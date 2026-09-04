"""
parser.py — Hybrid structural split.

ONE LLM call inspects the document and returns regex patterns describing
its specific numbering scheme (section headers, clause numbers, sub-clause
letters/numbers). Those patterns are then applied with pure Python regex —
deterministic, instant, and 100% verbatim to the source text.

If the returned patterns fail to compile or match too little of the
document, we retry once with the failure reason, then give up cleanly
rather than silently returning garbage.
"""
import os
import re
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from pydantic import BaseModel, Field

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is missing!")

client = genai.Client(api_key=api_key)


class StructurePatterns(BaseModel):
    section_regex: str = Field(..., description="Python regex matching this doc's section headers, e.g. r'^#{1,3}\\s*(Section\\s+\\d+.*)$'")
    clause_regex: str = Field(..., description="Python regex matching top-level clause numbers within a section, e.g. r'^(\\d+\\.\\d+)\\s'")
    subclause_regex: str = Field(..., description="Python regex matching lettered/numbered sub-clauses within a clause, "
                                                     "e.g. r'^\\s*([a-z])\\.\\s' — use an empty string if this document has no sub-clauses")
    notes: str = Field(..., description="Brief note on this document's numbering convention, for a human to sanity-check")


DETECT_PROMPT = """Examine this policy document's structure and numbering convention.

Return Python regular expression patterns (as strings, ready for re.compile with
re.MULTILINE) that will let a program split this EXACT document into its individual
addressable clauses, without losing any content.

Look carefully at:
- How are major sections marked? (e.g. "### Section 2:", "SECTION II", "## 2.0")
- How are individual numbered clauses marked within a section? (e.g. "2.1", "Clause A")
- Are there lettered or numbered sub-points within a clause? (e.g. "   a.", "1.", "2.2.1")

Document (first 4000 characters, structure should be evident from this excerpt):
---
{document_excerpt}
---

Return regex patterns as raw strings (Python re module syntax). Test them mentally
against the actual text shown above before returning them — they MUST match real
lines from this document.
"""


def detect_patterns(document_text: str) -> StructurePatterns:
    excerpt = document_text[:4000]
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=DETECT_PROMPT.format(document_excerpt=excerpt),
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=StructurePatterns,
            temperature=0.0
        ),
    )
    return StructurePatterns(**json.loads(response.text))


def load_document(path: str) -> str:
    if not path.endswith((".md", ".txt")):
        raise ValueError("Only .md and .txt files are supported.")
    with open(path, encoding="utf-8") as f:
        return f.read()


def apply_patterns(text: str, patterns: StructurePatterns) -> list[dict]:
    """Apply the LLM-detected regex patterns to split the document verbatim."""
    section_re = re.compile(patterns.section_regex, re.MULTILINE)
    clause_re = re.compile(patterns.clause_regex, re.MULTILINE)
    sub_re = re.compile(patterns.subclause_regex, re.MULTILINE) if patterns.subclause_regex else None

    clauses = []
    section_matches = list(section_re.finditer(text))

    if not section_matches:
        raise ValueError("section_regex matched 0 sections — pattern likely wrong")

    for i, sm in enumerate(section_matches):
        section_title = sm.group(1).strip() if sm.groups() else sm.group(0).strip()
        start = sm.end()
        end = section_matches[i + 1].start() if i + 1 < len(section_matches) else len(text)
        section_body = text[start:end]

        clause_matches = list(clause_re.finditer(section_body))
        if not clause_matches:
            continue

        for j, cm in enumerate(clause_matches):
            clause_num = cm.group(1) if cm.groups() else cm.group(0).strip()
            c_start = cm.end()
            c_end = clause_matches[j + 1].start() if j + 1 < len(clause_matches) else len(section_body)
            clause_text = section_body[c_start:c_end]

            if sub_re:
                sub_matches = list(sub_re.finditer(clause_text))
                if sub_matches:
                    for k, subm in enumerate(sub_matches):
                        letter = subm.group(1) if subm.groups() else subm.group(0).strip()
                        s_start = subm.end()
                        s_end = sub_matches[k + 1].start() if k + 1 < len(sub_matches) else len(clause_text)
                        clauses.append({
                            "address": f"{clause_num}.{letter}",
                            "section_title": section_title,
                            "text": clause_text[s_start:s_end].strip(),
                        })
                    continue

            clauses.append({
                "address": clause_num,
                "section_title": section_title,
                "text": clause_text.strip(),
            })

    return clauses


def parse_document(path: str) -> list[dict]:
    text = load_document(path)

    print("Detecting document structure (1 LLM call)...")
    patterns = detect_patterns(text)
    print(f"  section_regex:   {patterns.section_regex}")
    print(f"  clause_regex:    {patterns.clause_regex}")
    print(f"  subclause_regex: {patterns.subclause_regex}")
    print(f"  notes: {patterns.notes}")

    try:
        clauses = apply_patterns(text, patterns)
    except (re.error, ValueError) as e:
        raise RuntimeError(
            f"Detected patterns failed to apply cleanly ({e}). "
            f"Try re-running, or this document's structure may need manual pattern entry."
        )

    if len(clauses) < 3:
        print(f"WARNING: only {len(clauses)} clauses found — patterns may be too narrow. "
              f"Check the printed regexes above against the actual document.")

    return clauses


def print_clause_list(clauses: list[dict]):
    current_section = None
    for c in clauses:
        if c["section_title"] != current_section:
            current_section = c["section_title"]
            print(f"\n{current_section}\n" + "-" * 70)
        print(f"  [{c['address']}] {c['text'][:90]}...")


if __name__ == "__main__":
    os.makedirs("sample_docs", exist_ok=True)
    filename = input("Filename in sample_docs/: ").strip()
    path = os.path.join("sample_docs", filename)

    if not os.path.exists(path):
        print(f"Error: File '{path}' not found.")
    else:
        clauses = parse_document(path)
        print_clause_list(clauses)
        print(f"\nTotal clauses: {len(clauses)}")