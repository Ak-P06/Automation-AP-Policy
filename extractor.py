"""
extractor.py — Two-call per clause rule extraction.

Call 1: English clause + glossary → pseudo-code (free text, LLM thinks naturally)
Call 2: pseudo-code → rule dictionary (schema-constrained, mechanical conversion)

The pseudo-code step forces the LLM to make its logic explicit and use exact
glossary field names before the structured extraction happens — removing English
ambiguity before it can corrupt the rule structure.
"""
import os
import json
import logging
import time
from google import genai
from google.genai import types
from google.genai.errors import ClientError
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from typing import Optional

from schema import ComparisonOp, LogicalOp

load_dotenv()
logging.getLogger("google_genai").setLevel(logging.ERROR)

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing!")

client = genai.Client(api_key=api_key)

SECONDS_BETWEEN_CALLS = 4.5


# ---------- Schema for Call 2 output ----------

class SubCondition(BaseModel):
    field: str = Field(..., description="Must be an exact glossary field name")
    derivation: str | None = Field(None, description="Valid ANSI SQL expression using glossary fields, e.g., 'ABS(po_amount - grand_total_amount) / po_amount'")
    op: ComparisonOp
    value: str | float | None = None
    compare_to_field: str | None = None

class RuleCondition(BaseModel):
    operator: LogicalOp
    conditions: list[SubCondition]


class Action(BaseModel):
    type: str = Field(..., description="AUTO_APPROVE, ESCALATE, REJECT, HOLD, FLAG, NOTIFY")
    target: str | None = None
    reason_code: str | None = None
    requires_justification: bool = False


class Notification(BaseModel):
    trigger_source: str
    to: list[str]
    within_minutes: int | None = None


class ExtractedRule(BaseModel):
    description: str
    condition: RuleCondition
    actions: list[Action]
    exceptions: list[RuleCondition] = Field(default_factory=list)
    notifications: list[Notification] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)


class ExtractedRuleSet(BaseModel):
    rules: list[ExtractedRule] = Field(
        default_factory=list,
        description="Zero or more rules. Empty if the clause is purely narrative."
    )
    pseudo_code: str = Field(
        ...,
        description="The pseudo-code representation used to derive these rules."
    )


# ---------- Prompts ----------

PSEUDOCODE_PROMPT = """You are doing a WORD-FOR-WORD translation of ONE policy clause into pseudo-code.

Clause Address: {address}
Section: {section_title}
Clause Text:
---
{clause_text}
---

Available field names (use ONLY these exact names — no aliases, no abbreviations):
{glossary_text}

STEP 1 — Before writing pseudo-code, answer these two questions in one line each:
  Q1: Does this clause explicitly state a condition AND a consequence/action?
      (yes = has both; no = missing one or both)
  Q2: Does this clause state what happens in the NEGATIVE/failure case, or only the positive case?
      (both = has if AND else; positive-only = only says what to do when condition is met;
       negative-only = only says what to do when condition fails)

STEP 2 — Write the pseudo-code following these strict rules:
- WORD-FOR-WORD: translate ONLY what the clause explicitly says. Do not infer, add, or assume
  anything the clause does not directly state.
- NO IMPLIED ELSE: if the clause only states one side (e.g. only says what happens when
  something is missing, or only says what happens when it matches), write ONLY that IF/THEN.
  Do NOT add an ELSE branch — the other side belongs to a different clause.
- Use ONLY the field names listed above — no aliases, no abbreviations, no new names.
- For computed values, use STRICT ANSI SQL expression syntax inline (e.g., ABS(), COALESCE(), standard arithmetic) using exact glossary field names:
  e.g. IF ABS(grand_total_amount - po_amount) / po_amount >= 0.10 THEN ...
- Boundary wording matters precisely: "10% or more" = >=, "exceeds 10%" = >, "within 1%" = abs(...) <= 0.01.
- Multiple independent conditions in one clause = multiple separate IF/THEN blocks.
- AND conditions: IF condition1 AND condition2 THEN ...
- OR conditions: IF condition1 OR condition2 THEN ...
- Use ONLY the action words from the available actions list above in THEN blocks.
- If the clause has NO executable condition/action (purely a requirement statement, definition,
  or process description with no stated consequence), write: NO_RULE

Return ONLY the two Q&A lines from STEP 1 followed by the pseudo-code, nothing else.
"""

RULE_EXTRACTION_PROMPT = """Convert this pseudo-code into a structured rule dictionary.

Pseudo-code (may start with Q1/Q2 analysis lines — ignore those, only convert the IF/THEN blocks):
---
{pseudo_code}
---

Original clause text (for reference only — the pseudo-code is authoritative):
{clause_text}

Action vocabulary extracted from this document (use ONLY these action names in action.type):
{actions_text}

Rules for conversion:
- Ignore any lines starting with "Q1:" or "Q2:" — those are analysis notes, not rules.
- Each IF/THEN block becomes one rule in the "rules" list.
- "NO_RULE" or no IF/THEN blocks = return an empty rules list.
- condition.operator = "AND" or "OR" matching the pseudo-code logic.
- Each sub-condition in the IF part becomes one item in condition.conditions.
- If a condition uses a formula, extract it as a strictly valid ANSI SQL expression in "derivation", and put the primary field being evaluated as "field".
- action.type MUST be exactly one of the action names from the vocabulary above.
  Match the pseudo-code THEN statement to the closest action in the list.
- "confidence" = how clearly the pseudo-code maps to a deterministic rule (0.0-1.0).
  Lower it if the pseudo-code was ambiguous or the Q1/Q2 analysis flagged uncertainty.
- Also return the pseudo_code field unchanged (including Q1/Q2 lines if present).
- If a condition compares a field to a static number or literal word, put it in "value". 
- If a condition compares a field to ANOTHER dynamic field or system variable (like current_processing_date), put that variable name in "compare_to_field" and leave "value" null.

Return only JSON matching the schema.
"""


# ---------- Helpers ----------

def format_glossary(glossary: dict[str, str]) -> str:
    return "\n".join(f"  - {name}: {desc}" for name, desc in sorted(glossary.items()))


def call_with_retry(prompt: str, schema=None, max_retries: int = 5):
    config_args = {"temperature": 0.0}
    if schema:
        config_args["response_mime_type"] = "application/json"
        config_args["response_schema"] = schema

    for attempt in range(max_retries):
        try:
            return client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=prompt,
                config=types.GenerateContentConfig(**config_args),
            )
        except ClientError as e:
            if e.code == 429 and attempt < max_retries - 1:
                print(f"    Rate limited, waiting 20s (retry {attempt + 1}/{max_retries})...")
                time.sleep(20)
            else:
                raise
    raise RuntimeError("Max retries exceeded")


# ---------- Core extraction ----------

def generate_pseudo_code(clause: dict, glossary: dict[str, str]) -> str:
    """Call 1: English clause → pseudo-code (free text)."""
    response = call_with_retry(
        PSEUDOCODE_PROMPT.format(
            address=clause["address"],
            section_title=clause["section_title"],
            clause_text=clause["text"],
            glossary_text=format_glossary(glossary),
        )
    )
    return response.text.strip()


def extract_rules_from_pseudo(clause: dict, pseudo_code: str, actions_text: str) -> list[dict]:
    """Call 2: pseudo-code + action vocabulary → rule dict (schema-constrained)."""
    if "NO_RULE" in pseudo_code.upper() and "IF" not in pseudo_code.upper():
        return []

    rule_response = call_with_retry(
        RULE_EXTRACTION_PROMPT.format(
            pseudo_code=pseudo_code,
            clause_text=clause["text"],
            actions_text=actions_text,
        ),
        schema=ExtractedRuleSet,
    )

    try:
        result = json.loads(rule_response.text)
        rules = result.get("rules", [])
    except (json.JSONDecodeError, TypeError) as e:
        print(f"    WARNING: Failed to parse rule for [{clause['address']}]: {e}")
        return []

    for r in rules:
        r["source_clauses"] = [clause["address"]]
        r["raw_source_text"] = clause["text"]
        r["pseudo_code"] = pseudo_code

    return rules


def extract_all(clauses: list[dict], glossary: dict[str, str]) -> list[dict]:
    from action_extractor import extract_actions, format_actions_for_prompt, print_actions

    # Phase 1: generate all pseudo-code first
    print(f"\nPhase 1: Generating pseudo-code for {len(clauses)} clauses...")
    pseudo_codes = {}
    for clause in clauses:
        print(f"  [{clause['address']}] translating...")
        pseudo_codes[clause["address"]] = generate_pseudo_code(clause, glossary)
        time.sleep(SECONDS_BETWEEN_CALLS)

    # Phase 2: extract action vocabulary from all pseudo-code at once
    all_pseudo_list = [pc for pc in pseudo_codes.values() if pc]
    actions = extract_actions(all_pseudo_list)
    print_actions(actions)
    actions_text = format_actions_for_prompt(actions)
    time.sleep(SECONDS_BETWEEN_CALLS)

    # Phase 3: extract rules using glossary + action vocabulary
    print(f"\nPhase 3: Extracting rules from pseudo-code...")
    all_rules = []
    for clause in clauses:
        pseudo = pseudo_codes[clause["address"]]
        print(f"  [{clause['address']}] extracting...")
        rules = extract_rules_from_pseudo(clause, pseudo, actions_text)
        print(f"    -> {len(rules)} rule(s)")
        all_rules.extend(rules)
        time.sleep(SECONDS_BETWEEN_CALLS)

    return all_rules


# ---------- Main ----------

if __name__ == "__main__":
    from parser import parse_document
    from glossary_builder import build_glossary, print_glossary

    filename = input("Filename in sample_docs/: ").strip()
    path = os.path.join("sample_docs", filename)

    if not os.path.exists(path):
        print(f"Error: File '{path}' not found.")
    else:
        clauses = parse_document(path)
        glossary = build_glossary(clauses)
        print_glossary(glossary)

        rules = extract_all(clauses, glossary)

        print(f"\n{'='*70}")
        print(f"Total rules extracted: {len(rules)}")
        print(f"{'='*70}")
        for r in rules:
            print(json.dumps(r, indent=2))