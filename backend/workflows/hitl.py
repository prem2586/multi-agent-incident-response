
from uuid import uuid4
from typing import Any

from langgraph.types import Command

from backend.models.incident import Incident


# Graph initialized by FastAPI during startup.
_graph: Any = None


def set_graph(graph: Any) -> None:
    """Register the SQLite-backed LangGraph instance."""
    global _graph
    _graph = graph


def get_graph() -> Any:
    """Return the initialized graph."""
    if _graph is None:
        raise RuntimeError(
            "Incident graph not initialized. "
            "Start FastAPI or initialize the graph in tests."
        )
    return _graph


def make_config(thread_id: str) -> dict:
    return {
        "configurable": {
            "thread_id": thread_id,
        }
    }


async def start_incident(incident: Incident) -> dict:
    graph = get_graph()

    thread_id = f"{incident.incident_id}-{uuid4()}"

    result = await graph.ainvoke(
        {
            "incident": incident.model_dump(mode="json"),
            "status": "detected",
            "errors": [],
            "execution_results": [],
        },
        config=make_config(thread_id),
    )

    return {
        "thread_id": thread_id,
        "state": result,
    }


async def resume_incident(
    thread_id: str,
    decision: str,
    approved_by: str = "",
) -> dict:
    graph = get_graph()

    if decision not in ("approve", "reject"):
        raise ValueError("Decision must be approve or reject")

    if decision == "approve" and not approved_by.strip():
        raise ValueError("Approver identity required")

    config = make_config(thread_id)
    snapshot = await graph.aget_state(config)

    if "approval" not in snapshot.next:
        raise ValueError(
            "Incident is not awaiting approval"
        )

    result = await graph.ainvoke(
        Command(
            resume={
                "decision": decision,
                "approved_by": approved_by,
            }
        ),
        config=config,
    )

    return {
        "thread_id": thread_id,
        "state": result,
    }


async def get_incident_state(thread_id: str) -> dict:
    graph = get_graph()

    snapshot = await graph.aget_state(
        make_config(thread_id)
    )

    if not snapshot.values:
        raise ValueError("Workflow not found")

    return {
        "thread_id": thread_id,
        "state": snapshot.values,
        "next_nodes": list(snapshot.next),
    }
