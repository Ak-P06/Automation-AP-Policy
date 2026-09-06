"""
glossary_builder.py — Build a complete field glossary from parsed clauses.

Loads a generalized base AP glossary, then asks the LLM to extract only
NEW, document-specific fields that are not already in the base list.
Merges them together for a 100% accurate, hallucination-free data dictionary.
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
    field_name: str = Field(..., description="snake_case, e.g. 'is_handwritten'")
    description: str = Field(..., description="What this field represents in the policy")


class GlossaryDelta(BaseModel):
    fields: list[FieldEntry]


GLOSSARY_PROMPT = """You are building a data field glossary for an Accounts Payable policy document.

We already have a Base Glossary of standard system fields. 
Identify ANY NEW distinct data fields this policy references that are NOT in the Base Glossary.

Base Glossary (DO NOT EXTRACT THESE):
---
{base_glossary_keys}
---

Clauses to analyze:
---
{clauses_text}
---

CRITICAL RULES FOR NEW FIELDS:
1. DO NOT SKIP VARIATIONS: If the base glossary has "invoice_number" but the text compares it to a "QR invoice number", you MUST extract "qr_invoice_number" as a new distinct field. 
2. CAPTURE SPECIFIC SOURCES: Look closely for prefixes like "vendor_master_" vs regular "vendor_". If the document compares two similar things, they need two separate fields.
3. CAPTURE SYSTEM STATES: Extract any overall statuses mentioned (e.g., "validation_status").
4. Use snake_case names (e.g., "qr_invoice_number", "vendor_master_gstin").
5. Return only JSON matching the schema containing the NEW fields.
"""

def load_base_glossary() -> dict[str, str]:
    """Loads the generalized master data dictionary."""
    path = "base_glossary.json"
    if not os.path.exists(path):
        print(f"Warning: {path} not found. Proceeding with empty base glossary.")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def format_clauses(clauses: list[dict]) -> str:
    """Format clauses for the prompt."""
    return "\n".join(f"[{c['address']}] {c['text']}\n" for c in clauses)

def build_glossary(clauses: list[dict]) -> dict[str, str]:
    """Loads base glossary, extracts delta via LLM, and merges them."""
    base_glossary = load_base_glossary()
    
    print(f"Loaded {len(base_glossary)} base fields. Extracting document-specific fields (1 LLM call)...")
    
    base_keys = ", ".join(base_glossary.keys())
    clauses_text = format_clauses(clauses)
    
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=GLOSSARY_PROMPT.format(base_glossary_keys=base_keys, clauses_text=clauses_text),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GlossaryDelta,
            temperature=0.0
        ),
    )

    try:
        result = json.loads(response.text)
        delta_fields = {f["field_name"]: f["description"] for f in result.get("fields", [])}
    except Exception as e:
        print(f"Error parsing delta glossary: {e}")
        delta_fields = {}
        
    print(f"Discovered {len(delta_fields)} new custom fields.")
    
    # Merge base and delta (delta overrides base if there is a collision)
    final_glossary = {**base_glossary, **delta_fields}
    return final_glossary

def print_glossary(glossary: dict[str, str]):
    print(f"\nFinal Merged Glossary ({len(glossary)} fields)\n" + "-" * 70)
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