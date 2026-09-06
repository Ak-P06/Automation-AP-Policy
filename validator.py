"""
validator.py — Stage 5: Logic and Integrity Validation

Checks the structured RuleSet for:
1. Cross-reference integrity (do source clauses actually exist?)
2. Field integrity (parses SQL to ensure all variables exist in the glossary)
3. Logic conflicts (do identical conditions trigger different actions?)
"""
import json
import re
from schema import RuleSet, ValidationIssue

def extract_variables_from_sql(expression: str) -> list[str]:
    """
    Extracts snake_case variable names from an SQL expression.
    Ignores uppercase SQL functions (like SUBSTRING, ABS) and numbers.
    """
    if not expression:
        return []
    # Matches words that contain lowercase letters and underscores (standard glossary fields)
    variables = re.findall(r'\b[a-z][a-z0-9_]*\b', expression)
    # Filter out common SQL/JSON stopwords that might be lowercase
    stopwords = {"null", "true", "false", "and", "or", "select", "from"}
    return [v for v in variables if v not in stopwords]

def validate_ruleset(ruleset: RuleSet, original_clauses: list[dict]) -> RuleSet:
    print("\nValidating RuleSet integrity...")
    issues = []
    
    valid_addresses = {c["address"] for c in original_clauses}
    glossary_keys = set(ruleset.field_glossary.keys())
    
    # 1. Check Cross-References & Field Integrity
    for rule in ruleset.rules:
        # Check source clauses
        for clause in rule.source_clauses:
            if clause not in valid_addresses:
                issues.append(ValidationIssue(
                    issue_type="Missing Source Clause",
                    rule_ids=[rule.rule_id],
                    description=f"Source clause '{clause}' does not exist in the parsed document.",
                    severity="high"
                ))
        
        # Check field glossary adherence (including inside SQL formulas)
        for sub in rule.condition.conditions:
            
            # Check the primary field
            if sub.field not in glossary_keys:
                issues.append(ValidationIssue(
                    issue_type="Invented Field",
                    rule_ids=[rule.rule_id],
                    description=f"Field '{sub.field}' is not defined in the glossary.",
                    severity="critical"
                ))
                
            # Check variables inside SQL derivations
            for var in extract_variables_from_sql(sub.derivation):
                if var not in glossary_keys:
                    issues.append(ValidationIssue(
                        issue_type="Invented Field in Formula",
                        rule_ids=[rule.rule_id],
                        description=f"Variable '{var}' used in formula '{sub.derivation}' is not in the glossary.",
                        severity="critical"
                    ))
            
            # Check variables inside compare_to_field
            for var in extract_variables_from_sql(sub.compare_to_field):
                if var not in glossary_keys:
                    issues.append(ValidationIssue(
                        issue_type="Invented Field in Comparison",
                        rule_ids=[rule.rule_id],
                        description=f"Variable '{var}' used in comparison '{sub.compare_to_field}' is not in the glossary.",
                        severity="critical"
                    ))

    # 2. Detect Logic Conflicts (Same condition, different actions)
    condition_map = {}
    for rule in ruleset.rules:
        cond_str = rule.condition.model_dump_json(exclude_unset=True)
        action_str = json.dumps([a.model_dump(exclude_unset=True) for a in rule.actions], sort_keys=True)
        
        if cond_str not in condition_map:
            condition_map[cond_str] = []
        condition_map[cond_str].append((rule.rule_id, action_str))
        
    for cond_str, rule_data in condition_map.items():
        if len(rule_data) > 1:
            first_action = rule_data[0][1]
            conflicting_ids = [rid for rid, act in rule_data[1:] if act != first_action]
            
            if conflicting_ids:
                all_ids = [rule_data[0][0]] + conflicting_ids
                issues.append(ValidationIssue(
                    issue_type="Logic Conflict",
                    rule_ids=all_ids,
                    description="These rules share identical conditions but trigger different actions.",
                    severity="critical"
                ))

    print(f"Validation complete: Found {len(issues)} issues.")
    ruleset.issues = issues
    return ruleset