
import json
from pathlib import Path

from backend.models.incident import Incident
from backend.protocols.messages import (
    AgentRequest,
    AgentRole,
    AgentTask,
    MessageStatus,
)
from backend.agents.observability_agent import (
    run_observability_agent,
)
from backend.agents.knowledge_agent import (
    run_knowledge_agent,
)
from backend.agents.remediation_agent import (
    run_remediation_agent,
)


ROOT = Path(__file__).resolve().parents[1]


def load_incident():
    path = ROOT / "data/incidents/service_degradation.json"

    with path.open(encoding="utf-8") as file:
        return Incident.model_validate(json.load(file))


def make_request(incident_id, receiver, task, payload=None):
    return AgentRequest(
        incident_id=incident_id,
        correlation_id=incident_id,
        sender=AgentRole.COORDINATOR,
        receiver=receiver,
        task=task,
        payload=payload or {},
    )


def generate_plan(incident):
    obs_request = make_request(
        incident.incident_id,
        AgentRole.OBSERVABILITY,
        AgentTask.ANALYZE_TELEMETRY,
    )

    obs_response = run_observability_agent(
        obs_request, incident
    )

    knowledge_request = make_request(
        incident.incident_id,
        AgentRole.KNOWLEDGE,
        AgentTask.SEARCH_PAST_INCIDENTS,
    )

    knowledge_response = run_knowledge_agent(
        knowledge_request, incident
    )

    remediation_request = make_request(
        incident.incident_id,
        AgentRole.REMEDIATION,
        AgentTask.GENERATE_REMEDIATION,
        payload={
            "observability": obs_response.model_dump(mode="json"),
            "knowledge": knowledge_response.model_dump(mode="json"),
        },
    )

    return run_remediation_agent(
        remediation_request, incident
    )


def test_checkout_remediation_plan():
    incident = load_incident()
    response = generate_plan(incident)

    assert response.status == MessageStatus.COMPLETED

    plan = response.metadata["remediation_plan"]

    assert plan["execution_allowed"] is False
    assert plan["requires_human_approval"] is True

    actions = plan["actions"]

    assert len(actions) >= 2

    assert actions[0]["action_type"] == (
        "verify_database_connections"
    )

    assert actions[1]["action_type"] == (
        "rollback_deployment"
    )

    assert actions[1]["prerequisites"] == ["ACT-001"]

    assert all(
        action["requires_approval"]
        for action in actions
    )

    print("\nREMEDIATION PLAN")
    print(json.dumps(plan, indent=2))


def test_missing_evidence():
    incident = load_incident()

    incident.logs = []
    incident.metrics = []

    response = generate_plan(incident)

    assert response.status == MessageStatus.PARTIAL

    plan = response.metadata["remediation_plan"]

    assert plan["execution_allowed"] is False
    assert plan["missing_information"]


def test_invalid_remediation_request():
    incident = load_incident()

    request = make_request(
        incident.incident_id,
        AgentRole.REMEDIATION,
        AgentTask.GENERATE_REMEDIATION,
        payload={},
    )

    response = run_remediation_agent(request, incident)

    assert response.status == MessageStatus.FAILED
    assert response.error is not None
