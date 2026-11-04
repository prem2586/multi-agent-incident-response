
import asyncio
import json
from pathlib import Path

from backend.models.incident import Incident
from backend.coordinator.coordinator_agent import (
    IncidentCoordinator,
)
from backend.protocols.messages import (
    AgentRole,
    MessageStatus,
)


ROOT = Path(__file__).resolve().parents[1]


def load_incident():
    path = ROOT / "data/incidents/service_degradation.json"

    with path.open(encoding="utf-8") as file:
        return Incident.model_validate(json.load(file))


def test_end_to_end_coordinator():
    incident = load_incident()

    result = asyncio.run(
        IncidentCoordinator().investigate(incident)
    )

    assert result.status == "awaiting_approval"
    assert result.execution_allowed is False

    assert len(result.agent_responses) == 3

    assert (
        result.agent_responses["observability_agent"].status
        == MessageStatus.COMPLETED
    )

    assert (
        result.agent_responses["knowledge_agent"].status
        == MessageStatus.COMPLETED
    )

    assert (
        result.agent_responses["remediation_agent"].status
        == MessageStatus.COMPLETED
    )

    plan = result.remediation_plan

    assert plan["execution_allowed"] is False
    assert plan["requires_human_approval"] is True
    assert len(plan["actions"]) >= 2

    print("\nCOORDINATOR RESULT")
    print(result.model_dump_json(indent=2))


def test_partial_telemetry():
    incident = load_incident()
    incident.logs = []
    incident.metrics = []

    result = asyncio.run(
        IncidentCoordinator().investigate(incident)
    )

    assert result.status == "partial"
    assert result.execution_allowed is False
    assert result.missing_information


def test_agent_failure(monkeypatch):
    from backend.coordinator import handoff

    original_handler = handoff.AGENT_REGISTRY[
        AgentRole.KNOWLEDGE
    ]

    def failing_knowledge_agent(request, incident):
        raise RuntimeError("Knowledge service unavailable")

    monkeypatch.setitem(
        handoff.AGENT_REGISTRY,
        AgentRole.KNOWLEDGE,
        failing_knowledge_agent,
    )

    incident = load_incident()

    result = asyncio.run(
        IncidentCoordinator().investigate(incident)
    )

    assert result.status == "partial_failure"
    assert result.execution_allowed is False

    assert any(
        "knowledge_agent" in error
        for error in result.errors
    )

    assert (
        result.agent_responses["observability_agent"].status
        == MessageStatus.COMPLETED
    )
