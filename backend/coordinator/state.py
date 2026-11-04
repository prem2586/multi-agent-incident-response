
from datetime import datetime, timezone
from pydantic import BaseModel, Field

from backend.protocols.messages import AgentResponse


class CoordinatorResult(BaseModel):
    incident_id: str
    correlation_id: str
    status: str
    root_cause_hypothesis: str | None = None

    agent_responses: dict[str, AgentResponse] = Field(
        default_factory=dict
    )

    remediation_plan: dict = Field(default_factory=dict)

    missing_information: list[str] = Field(
        default_factory=list
    )

    errors: list[str] = Field(default_factory=list)

    execution_allowed: bool = False

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
