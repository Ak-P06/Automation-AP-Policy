from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ComparisonOp(str, Enum):
    GT = ">"
    GTE = ">="
    LT = "<"
    LTE = "<="
    EQ = "=="
    NEQ = "!="


class LogicalOp(str, Enum):
    AND = "AND"
    OR = "OR"


class SubCondition(BaseModel):
    field: str = Field(..., description="Field name being compared")
    derivation: Optional[str] = Field(None, description="Formula if computed")
    op: ComparisonOp
    value: str | float = Field(..., description="Threshold value")


class RuleCondition(BaseModel):
    """Always this one shape. Single-field check = 1 item in conditions, operator AND."""
    operator: LogicalOp
    conditions: list[SubCondition]


class Action(BaseModel):
    type: str = Field(..., description="AUTO_APPROVE, ESCALATE, REJECT, HOLD, FLAG")
    target: Optional[str] = Field(None, description="Who it routes to")
    reason_code: Optional[str] = Field(None, description="Reason from doc")
    requires_justification: bool = False


class Notification(BaseModel):
    trigger_source: str = Field(..., description="Which clause requires this")
    to: list[str]
    within_minutes: Optional[int] = None
    fields_required: list[str] = Field(default_factory=list)


class Rule(BaseModel):
    rule_id: str
    source_clauses: list[str]
    description: str
    condition: RuleCondition
    action: Action
    exceptions: list[RuleCondition] = Field(default_factory=list)
    notifications: list[Notification] = Field(default_factory=list)
    conflict_group: Optional[str] = None
    confidence: float = Field(..., ge=0.0, le=1.0)
    raw_source_text: str


class ValidationIssue(BaseModel):
    issue_type: str
    rule_ids: list[str]
    description: str
    severity: str = "medium"


class RuleSet(BaseModel):
    document_name: str
    field_glossary: dict[str, str] = Field(default_factory=dict)
    rules: list[Rule]
    issues: list[ValidationIssue] = Field(default_factory=list)