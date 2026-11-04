
import json
from pathlib import Path

import pytest

from backend.models.incident import Incident, IncidentType
from backend.agents.knowledge_agent import (
    run_knowledge_agent,
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
        receiver=AgentRole.KNOWLEDGE,
        task=AgentTask.SEARCH_PAST_INCIDENTS,
        payload={"top_k": 3},
    )


def test_retrieves_checkout_history():
    incident = load_incident()
    request = create_request(incident.incident_id)

    response = run_knowledge_agent(
        request=request,
        incident=incident,
    )

    assert response.status == MessageStatus.COMPLETED
    assert response.request_message_id == request.message_id
    assert response.confidence > 0

    matches = response.metadata["matched_incidents"]

    assert matches
    assert matches[0]["incident_id"] == "HIST-001"

    assert any(
        item["runbook_id"] == "RB-001"
        for item in response.metadata["retrieved_runbooks"]
    )

    print("\nKNOWLEDGE AGENT RESULT")
    print(response.model_dump_json(indent=2))



def test_handles_no_matching_incidents():
    incident = load_incident()

    incident.title = "Unknown quantum subsystem anomaly"
    incident.description = "Unrecognized quantum subsystem behavior"
    incident.affected_services = ["quantum-service"]
    incident.logs = []
    incident.metrics = []

    incident.incident_type = (
        IncidentType.INFRASTRUCTURE_FAILURE
    )

    request = create_request(incident.incident_id)

    response = run_knowledge_agent(
        request=request,
        incident=incident,
    )

    assert response.status == MessageStatus.PARTIAL
    assert response.confidence == 0.0
    assert not response.metadata["matched_incidents"]



def test_invalid_request_receiver():
    incident = load_incident()

    request = AgentRequest(
        incident_id=incident.incident_id,
        correlation_id=incident.incident_id,
        sender=AgentRole.COORDINATOR,
        receiver=AgentRole.OBSERVABILITY,
        task=AgentTask.SEARCH_PAST_INCIDENTS,
    )

    with pytest.raises(ValueError):
        run_knowledge_agent(request, incident)


def test_missing_knowledge_base(monkeypatch, tmp_path):
    import backend.tools.incident_search as search_module

    monkeypatch.setattr(
        search_module,
        "KB_DIR",
        tmp_path,
    )

    incident = load_incident()
    request = create_request(incident.incident_id)

    response = run_knowledge_agent(
        request=request,
        incident=incident,
    )

    assert response.status == MessageStatus.FAILED
    assert response.error is not None
