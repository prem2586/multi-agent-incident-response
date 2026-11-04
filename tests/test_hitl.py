
import asyncio
import json
from pathlib import Path

import pytest

from backend.models.incident import Incident
from backend.models.remediation import RemediationPlan
import pytest
from langgraph.checkpoint.memory import MemorySaver

from backend.workflows.incident_graph import build_incident_graph
from backend.workflows.hitl import set_graph
from backend.services.simulation_executor import (
    execute_simulated_plan,
)
from backend.workflows.hitl import (
    start_incident,
    resume_incident,
    get_incident_state,
)


ROOT = Path(__file__).resolve().parents[1]


def load_incident():
    path = ROOT / "data/incidents/service_degradation.json"

    with path.open(encoding="utf-8") as file:
        return Incident.model_validate(json.load(file))


def test_workflow_pauses_for_approval():
    async def scenario():
        started = await start_incident(load_incident())
        thread_id = started["thread_id"]

        snapshot = await get_incident_state(thread_id)

        assert "approval" in snapshot["next_nodes"]
        assert snapshot["state"]["execution_results"] == []

        return thread_id

    thread_id = asyncio.run(scenario())
    assert thread_id


def test_approval_executes_simulation():
    async def scenario():
        started = await start_incident(load_incident())

        result = await resume_incident(
            thread_id=started["thread_id"],
            decision="approve",
            approved_by="capstone_operator",
        )

        state = result["state"]

        assert state["status"] == "simulated_resolved"
        assert len(state["execution_results"]) >= 2
        assert all(
            item["simulation_only"]
            for item in state["execution_results"]
        )

    asyncio.run(scenario())


def test_rejection_blocks_execution():
    async def scenario():
        started = await start_incident(load_incident())

        result = await resume_incident(
            thread_id=started["thread_id"],
            decision="reject",
        )

        state = result["state"]

        assert state["status"] == "rejected"
        assert state["execution_results"] == []

    asyncio.run(scenario())


def test_direct_execution_without_approval():
    plan = RemediationPlan(
        incident_id="INC-TEST",
        root_cause_hypothesis="Test",
        confidence=0.5,
        actions=[],
    )

    with pytest.raises(PermissionError):
        execute_simulated_plan(
            plan=plan,
            approved=False,
        )


def test_invalid_approval_identity():
    async def scenario():
        started = await start_incident(load_incident())

        with pytest.raises(ValueError):
            await resume_incident(
                thread_id=started["thread_id"],
                decision="approve",
                approved_by="",
            )

        snapshot = await get_incident_state(
            started["thread_id"]
        )

        assert "approval" in snapshot["next_nodes"]

    asyncio.run(scenario())




@pytest.fixture(autouse=True)
def initialize_test_graph():
    graph = build_incident_graph(MemorySaver())
    set_graph(graph)

    yield

    set_graph(None)    
