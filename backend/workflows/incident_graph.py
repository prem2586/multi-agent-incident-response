
from typing import Any, TypedDict

from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt

from backend.models.incident import Incident
from backend.models.remediation import RemediationPlan
from typing import NotRequired
from backend.coordinator.coordinator_agent import IncidentCoordinator
from backend.services.simulation_executor import (
    execute_simulated_plan,
)
from backend.tools.postmortem_generator import (
    generate_postmortem,
    save_postmortem,
)




class IncidentGraphState(TypedDict, total=False):
    incident: dict[str, Any]
    coordinator_result: dict[str, Any]
    remediation_plan: dict[str, Any]
    approval_decision: str
    approved_by: str
    execution_results: list[dict[str, Any]]
    status: str
    errors: list[str]
    postmortem_report: NotRequired[str]
    postmortem_path: NotRequired[str]


async def investigate_node(
    state: IncidentGraphState,
) -> dict:
    incident = Incident.model_validate(
        state["incident"]
    )

    result = await IncidentCoordinator().investigate(
        incident
    )

    coordinator_data = result.model_dump(mode="json")

    return {
        "coordinator_result": coordinator_data,
        "remediation_plan": coordinator_data[
            "remediation_plan"
        ],
        "status": result.status,
        "errors": result.errors,
    }


def approval_node(
    state: IncidentGraphState,
) -> dict:
    plan = state.get("remediation_plan", {})

    if not plan.get("actions"):
        return {
            "approval_decision": "unavailable",
            "status": "investigation_incomplete",
        }

    # LangGraph persists state and pauses here.
    decision = interrupt({
        "type": "human_approval_required",
        "incident_id": state["incident"]["incident_id"],
        "root_cause_hypothesis": plan.get(
            "root_cause_hypothesis"
        ),
        "actions": plan["actions"],
        "message": "Approve or reject simulated remediation",
    })

    if not isinstance(decision, dict):
        return {
            "approval_decision": "rejected",
            "status": "rejected",
        }

    approved = decision.get("decision") == "approve"
    approved_by = decision.get("approved_by", "")

    if not approved or not isinstance(approved_by, str):
        return {
            "approval_decision": "rejected",
            "status": "rejected",
        }

    if not approved_by.strip():
        return {
            "approval_decision": "rejected",
            "status": "rejected",
        }

    return {
        "approval_decision": "approved",
        "approved_by": approved_by.strip(),
        "status": "approved",
    }


def route_after_approval(
    state: IncidentGraphState,
) -> str:
    if state.get("approval_decision") == "approved":
        return "execute"
    return "finish"


def execute_node(
    state: IncidentGraphState,
) -> dict:
    if state.get("approval_decision") != "approved":
        return {
            "status": "rejected",
            "execution_results": [],
        }

    plan = RemediationPlan.model_validate(
        state["remediation_plan"]
    )

    try:
        results = execute_simulated_plan(
            plan=plan,
            approved=True,
        )

        return {
            "execution_results": results,
            "status": "simulated_resolved",
        }

    except Exception as exc:
        return {
            "execution_results": [],
            "status": "execution_failed",
            "errors": state.get("errors", []) + [str(exc)],
        }


def build_incident_graph(checkpointer):
    builder = StateGraph(IncidentGraphState)

    builder.add_node("investigate", investigate_node)
    builder.add_node("approval", approval_node)
    builder.add_node("execute", execute_node)

    builder.add_edge(START, "investigate")
    builder.add_edge("investigate", "approval")
    builder.add_node("postmortem", postmortem_node)



    builder.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "execute": "execute",
            "finish": "postmortem",
        },
    )

    builder.add_edge("execute", "postmortem")
    builder.add_edge("postmortem", END)
    return builder.compile(checkpointer=checkpointer)

async def postmortem_node(state: dict) -> dict:
    incident = state.get("incident")
    coordinator_result = state.get("coordinator_result")

    report = generate_postmortem(
        incident=incident,
        coordinator_result=coordinator_result,
        workflow_state=state,
    )

    incident_data = (
        incident.model_dump(mode="json")
        if hasattr(incident, "model_dump")
        else incident
    ) or {}

    incident_id = incident_data.get(
        "incident_id", "unknown"
    )

    path = save_postmortem(
        incident_id=incident_id,
        report=report,
    )

    return {
        "postmortem_report": report,
        "postmortem_path": str(path),
    }
