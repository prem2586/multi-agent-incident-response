
from enum import Enum
from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActionStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class RemediationAction(BaseModel):
    action_id: str
    action_type: str
    description: str
    priority: int = Field(ge=1)
    risk: RiskLevel
    requires_approval: bool = True
    status: ActionStatus = ActionStatus.PROPOSED
    prerequisites: list[str] = Field(default_factory=list)
    rollback_plan: str
    rationale: str
    evidence_sources: list[str] = Field(default_factory=list)


class RemediationPlan(BaseModel):
    incident_id: str
    root_cause_hypothesis: str
    confidence: float = Field(ge=0.0, le=1.0)
    actions: list[RemediationAction] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    requires_human_approval: bool = True
    execution_allowed: bool = False
