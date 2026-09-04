"""
action_extractor.py — Extract the complete action vocabulary from pseudo-code.

Takes all pseudo-code strings generated in extractor.py's Call 1, sends them
in one batch to the LLM, and asks: "What distinct actions does this policy use?"

Returns a normalized action list that Call 2 uses as its constrained vocabulary
— fully document-specific, no hardcoding.
"""
import os
import json
import logging
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()
logging.getLogger("google_genai").setLevel(logging.ERROR)

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing!")

client = genai.Client(api_key=api_key)


class ActionEntry(BaseModel):
    action_name: str = Field(
        ...,
        description="UPPER_SNAKE_CASE normalized action name, e.g. REJECT, HOLD, ESCALATE_TO_FINANCE_CONTROLLER"
    )
    description: str = Field(
        ...,
        description="What this action means in this policy"
    )
    pseudo_code_triggers: list[str] = Field(
        ...,
        description="Exact phrases from the pseudo-code that map to this action, e.g. ['REJECT invoice', 'SET status = Awaiting GRN']"
    )


class ActionVocabulary(BaseModel):
    actions: list[ActionEntry]


ACTION_PROMPT = """Below are pseudo-code translations of all clauses from a policy document.

Identify every distinct ACTION VERB or CONSEQUENCE the policy specifies — things the system
must DO when a condition is met (reject, hold, route to someone, flag, approve, notify, etc.)

Pseudo-code from all clauses:
---
{all_pseudo_code}
---

Rules:
- Normalize action names to BASE VERBS in UPPER_SNAKE_CASE (e.g., REJECT, HOLD, FLAG, ESCALATE, AUTO_APPROVE, NOTIFY).
- DO NOT create compound actions with targets (Wrong: ESCALATE_TO_CFO. Right: ESCALATE). Targets and reason codes will be handled separately in the next phase.
- If multiple pseudo-code phrases mean the same action (e.g., "REJECT invoice" and
  "REJECT WITH REASON X" are both just REJECT), merge them into one entry.
- Include NO_RULE as an action only if it appears — it means "this clause produces no rule."
- List "pseudo_code_triggers": the exact phrases from the pseudo-code that map to this action.

Return only JSON matching the schema.
"""


def extract_actions(pseudo_codes: list[str]) -> list[dict]:
    """One LLM call: extract all actions from all pseudo-code strings."""
    print("Extracting action vocabulary from pseudo-code (1 LLM call)...")

    all_pseudo = "\n\n---\n\n".join(
        f"[Clause {i+1}]:\n{pc}" for i, pc in enumerate(pseudo_codes) if pc
    )

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=ACTION_PROMPT.format(all_pseudo_code=all_pseudo),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=ActionVocabulary,
            temperature=0.0
        ),
    )

    result = json.loads(response.text)
    return result["actions"]


def format_actions_for_prompt(actions: list[dict]) -> str:
    """Format action list for injection into Call 2's extraction prompt."""
    lines = []
    for a in actions:
        triggers = ", ".join(f'"{t}"' for t in a.get("pseudo_code_triggers", [])[:3])
        lines.append(f"  - {a['action_name']}: {a['description']} (triggers: {triggers})")
    return "\n".join(lines)


def print_actions(actions: list[dict]):
    print(f"\nAction Vocabulary ({len(actions)} actions)\n" + "-" * 70)
    for a in actions:
        print(f"  {a['action_name']:<35} {a['description']}")
        for t in a.get("pseudo_code_triggers", []):
            print(f"    trigger: \"{t}\"")
