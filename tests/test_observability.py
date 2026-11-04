
import json
from pathlib import Path

from backend.models.incident import Incident
from backend.agents.observability_agent import (
    run_observability_agent,
)
from backend.protocols.messages import (
    AgentRequest,
    AgentRole,
    AgentTask,
    MessageStatus,
)


ROOT = Path(__file__).resolve().parents[1]


def load_incident() -> Incident:
    path = (
        ROOT
        / "data"
        / "incidents"
        / "service_degradation.json"
    )

    with path.open(encoding="utf-8") as file:
        return Incident.model_validate(json.load(file))


def create_request(incident_id: str) -> AgentRequest:
    return AgentRequest(
        incident_id=incident_id,
        correlation_id=incident_id,
        sender=AgentRole.COORDINATOR,
        receiver=AgentRole.OBSERVABILITY,
        task=AgentTask.ANALYZE_TELEMETRY,
        payload={"service": "checkout-service"},
    )


def test_checkout_degradation():
    incident = load_incident()
    request = create_request(incident.incident_id)

    response = run_observability_agent(
        request=request,
        incident=incident,
    )

    assert response.status == MessageStatus.COMPLETED
    assert response.incident_id == "INC-001"
    assert response.request_message_id == request.message_id
    assert response.confidence == 1.0

    assert any(
        "17.5x" in finding
        for finding in response.findings
    )

    assert any(
        "connection pool" in finding.lower()
        for finding in response.findings
    )

    print("\nOBSERVABILITY AGENT RESULT")
    print(response.model_dump_json(indent=2))


def test_partial_telemetry():
    incident = load_incident()

    incident.metrics = [
        metric for metric in incident.metrics
        if metric.name != "db_connection_pool_utilization"
    ]

    request = create_request(incident.incident_id)

    response = run_observability_agent(
        request=request,
        incident=incident,
    )

    assert response.status == MessageStatus.PARTIAL
    assert response.confidence < 1.0

    assert any(
        "Database connection pool" in item
        for item in response.missing_information
    )


def test_empty_telemetry():
    incident = load_incident()
    incident.logs = []
    incident.metrics = []

    request = create_request(incident.incident_id)

    response = run_observability_agent(
        request=request,
        incident=incident,
    )

    assert response.status == MessageStatus.PARTIAL
    assert response.confidence == 0.0
    assert response.missing_information
