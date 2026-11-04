
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ConfigDict


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    DETECTED = "detected"
    TRIAGING = "triaging"
    INVESTIGATING = "investigating"
    PLANNING = "planning"
    AWAITING_APPROVAL = "awaiting_approval"
    REMEDIATING = "remediating"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    FAILED = "failed"


class IncidentType(str, Enum):
    SERVICE_DEGRADATION = "service_degradation"
    SECURITY_ALERT = "security_alert"
    INFRASTRUCTURE_FAILURE = "infrastructure_failure"


class Metric(BaseModel):
    name: str
    value: float
    unit: str
    timestamp: datetime


class LogEntry(BaseModel):
    timestamp: datetime
    level: str
    service: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Incident(BaseModel):
    model_config = ConfigDict(extra="forbid")

    incident_id: str
    title: str
    description: str

    incident_type: IncidentType
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.DETECTED

    affected_services: list[str] = Field(default_factory=list)

    detected_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    metrics: list[Metric] = Field(default_factory=list)
    logs: list[LogEntry] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(default_factory=dict)

    root_cause: str | None = None
    resolution: str | None = None

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def update_status(self, new_status: IncidentStatus) -> None:
        self.status = new_status
        self.updated_at = datetime.now(timezone.utc)

    def add_metric(self, metric: Metric) -> None:
        self.metrics.append(metric)
        self.updated_at = datetime.now(timezone.utc)

    def add_log(self, log: LogEntry) -> None:
        self.logs.append(log)
        self.updated_at = datetime.now(timezone.utc)
