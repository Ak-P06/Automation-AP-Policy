"""
structurer.py — Stage 4: Rule ID assignment and final JSON compilation.

Takes the raw extracted rules from Stage 3, assigns clean, sequential 
deterministic IDs (e.g., AP-001, AP-002), and wraps everything into the 
final RuleSet schema ready for Stage 5 validation.
"""
import json
from schema import RuleSet, Rule

def structure_rules(document_name: str, glossary: dict[str, str], raw_rules: list[dict]) -> RuleSet:
    """Assigns sequential rule IDs and compiles the final RuleSet structure."""
    print("\nStructuring rules and assigning deterministic IDs...")
    formatted_rules = []
    
    for index, raw_rule in enumerate(raw_rules, start=1):
        rule_id = f"AP-{index:03d}"  # Generates AP-001, AP-002, etc.
        
        # Build the rule model, mapping raw dict fields to the final Pydantic schema
        rule_data = {
            "rule_id": rule_id,
            "source_clauses": raw_rule.get("source_clauses", []),
            "description": raw_rule.get("description", "No description provided."),
            "condition": raw_rule.get("condition"),
            "actions": raw_rule.get("actions", []),
            "exceptions": raw_rule.get("exceptions", []),
            "notifications": raw_rule.get("notifications", []),
            "conflict_group": raw_rule.get("conflict_group"),
            "confidence": raw_rule.get("confidence", 1.0),
            "raw_source_text": raw_rule.get("raw_source_text", ""),
        }
        
        try:
            # Validate through Pydantic
            validated_rule = Rule(**rule_data)
            formatted_rules.append(validated_rule)
        except Exception as e:
            print(f"  [ERROR] Failed to validate rule {rule_id} against schema: {e}")
            # In a production environment, you might append this to an error log
            continue

    print(f"Successfully structured {len(formatted_rules)} rules.")

    # Wrap in the final RuleSet schema
    return RuleSet(
        document_name=document_name,
        field_glossary=glossary,
        rules=formatted_rules,
        issues=[]  # Issues will be populated in Stage 5 (Validator)
    )

if __name__ == "__main__":
    print("structurer.py is ready to compile rules into the RuleSet schema.")
    print("Run main.py to execute the full pipeline.")