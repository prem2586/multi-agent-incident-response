
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, ConfigDict


class AgentRole(str, Enum):
    COORDINATOR = "coordinator"
    OBSERVABILITY = "observability_agent"
    KNOWLEDGE = "knowledge_agent"
    REMEDIATION = "remediation_agent"


class MessageStatus(str, Enum):
    REQUESTED = "requested"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class AgentTask(str, Enum):
    ANALYZE_TELEMETRY = "analyze_telemetry"
    SEARCH_PAST_INCIDENTS = "search_past_incidents"
    GENERATE_REMEDIATION = "generate_remediation"


class Evidence(BaseModel):
    source: str
    description: str
    value: Any = None


class AgentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    incident_id: str
    correlation_id: str

    sender: AgentRole
    receiver: AgentRole

    task: AgentTask

    payload: dict[str, Any] = Field(default_factory=dict)

    status: MessageStatus = MessageStatus.REQUESTED

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AgentResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(
        default_factory=lambda: str(uuid4())
    )

    request_message_id: str

    incident_id: str
    correlation_id: str

    sender: AgentRole
    receiver: AgentRole

    status: MessageStatus

    findings: list[str] = Field(default_factory=list)

    evidence: list[Evidence] = Field(default_factory=list)

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0
    )

    missing_information: list[str] = Field(
        default_factory=list
    )

    recommended_next_action: str | None = None

    error: str | None = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
