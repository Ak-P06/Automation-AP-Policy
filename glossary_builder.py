"""
glossary.py — Build a complete field glossary from parsed clauses.

Takes the clause list from parser.py, sends ALL clauses to the LLM once,
asks: "What data fields does this policy reference?" Returns a complete
field glossary {field_name: description} for use by extractor.py.

No rule extraction, no drafting — just field identification.
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


class FieldEntry(BaseModel):
    field_name: str = Field(..., description="snake_case, e.g. 'invoice_total'")
    description: str = Field(..., description="What this field represents in the policy")


class Glossary(BaseModel):
    fields: list[FieldEntry]


GLOSSARY_PROMPT = """You are building a data field glossary for a policy document.

Below are all the clauses from the policy. Identify EVERY distinct data field the policy
references or implies — values a system would need to look up, compute, or check to
evaluate the policy's rules.

Clauses:
---
{clauses_text}
---

Rules for the glossary:
- Use snake_case names (e.g. "invoice_total", "po_amount", "variance_pct", "vendor_gstin").
- If two parts of the document refer to the same concept using different words
  (e.g. "Invoice Total Amount" vs "Grand Total"), use ONE field name — do not create duplicates.
- Include fields that matter for evaluating rules (amounts, quantities, dates, percentages,
  IDs, statuses, categorical flags like "supply_type" or "vendor_on_watchlist").
- Skip purely narrative/metadata text (document titles, sign-off names, section headers).
- Pay special attention to CATEGORICAL/GATING fields that determine which rules apply
  (e.g. "supply_type: intra-state vs inter-state", "po_type: goods vs services").

Return only JSON matching the schema.
"""


def format_clauses(clauses: list[dict]) -> str:
    """Format clauses for the prompt."""
    lines = []
    for c in clauses:
        lines.append(f"[{c['address']}] {c['section_title']}")
        lines.append(c['text'])
        lines.append("")
    return "\n".join(lines)


def build_glossary(clauses: list[dict]) -> dict[str, str]:
    """One LLM call: extract all fields from all clauses."""
    print("Building glossary from all clauses (1 LLM call)...")
    
    clauses_text = format_clauses(clauses)
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=GLOSSARY_PROMPT.format(clauses_text=clauses_text),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Glossary,
            temperature=0.0
        ),
    )

    result = json.loads(response.text)
    return {f["field_name"]: f["description"] for f in result["fields"]}


def print_glossary(glossary: dict[str, str]):
    print(f"\nGlossary ({len(glossary)} fields)\n" + "-" * 70)
    for name, desc in sorted(glossary.items()):
        print(f"  {name:<28} {desc}")


if __name__ == "__main__":
    from parser import parse_document

    filename = input("Filename in sample_docs/: ").strip()
    path = os.path.join("sample_docs", filename)

    if not os.path.exists(path):
        print(f"Error: File '{path}' not found.")
    else:
        clauses = parse_document(path)
        glossary = build_glossary(clauses)
        print_glossary(glossary)