"""
main.py — End-to-End AP Policy Automation Pipeline

Orchestrates the 5-stage pipeline:
1. Parser (Split text via Regex)
2. Glossary Builder (Extract custom fields + Base Glossary)
3. Extractor (Pseudo-code -> JSON Rules)
4. Structurer (Assign IDs & Format)
5. Validator (Integrity & Conflict Checks)
"""
import os
from parser import parse_document
from glossary_builder import build_glossary
from extractor import extract_all
from structurer import structure_rules
from validator import validate_ruleset

def run_pipeline(filename: str):
    filepath = os.path.join("sample_docs", filename)
    if not os.path.exists(filepath):
        print(f"Error: {filepath} not found.")
        return

    print(f"\n{'='*60}")
    print(f" STARTING PIPELINE: {filename}")
    print(f"{'='*60}")
    
    # Stage 1: Parse
    print("\n[STAGE 1] Parsing Document...")
    clauses = parse_document(filepath)
    
    # Stage 2: Glossary
    print("\n[STAGE 2] Building Glossary...")
    glossary = build_glossary(clauses)
    
    # Stage 3: Extract Rules
    print("\n[STAGE 3] Extracting Rules...")
    raw_rules = extract_all(clauses, glossary)
    
    # Stage 4: Structure
    print("\n[STAGE 4] Structuring Rules...")
    ruleset = structure_rules(filename, glossary, raw_rules)
    
    # Stage 5: Validate
    print("\n[STAGE 5] Validating Rules...")
    final_ruleset = validate_ruleset(ruleset, clauses)
    
    # Export File
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"{filename.split('.')[0]}_rules.json")
    
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(final_ruleset.model_dump_json(indent=2))
        
    print(f"\n{'='*60}")
    print(f" PIPELINE COMPLETE! ")
    print(f" Total Rules: {len(final_ruleset.rules)}")
    print(f" Validation Issues: {len(final_ruleset.issues)}")
    print(f" Saved to: {out_file}")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    doc_name = input("Enter document filename in sample_docs/ (e.g., sample.md): ").strip()
    run_pipeline(doc_name)