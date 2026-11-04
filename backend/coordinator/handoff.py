
import asyncio
from functools import partial

from backend.models.incident import Incident
from backend.protocols.messages import (
    AgentRequest,
    AgentResponse,
    AgentRole,
    AgentTask,
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


AGENT_REGISTRY = {
    AgentRole.OBSERVABILITY: run_observability_agent,
    AgentRole.KNOWLEDGE: run_knowledge_agent,
    AgentRole.REMEDIATION: run_remediation_agent,
}


def create_agent_request(
    incident_id: str,
    correlation_id: str,
    receiver: AgentRole,
    task: AgentTask,
    payload: dict | None = None,
) -> AgentRequest:
    return AgentRequest(
        incident_id=incident_id,
        correlation_id=correlation_id,
        sender=AgentRole.COORDINATOR,
        receiver=receiver,
        task=task,
        payload=payload or {},
    )


async def dispatch_agent(
    request: AgentRequest,
    incident: Incident,
    timeout_seconds: float = 15.0,
) -> AgentResponse:
    """
    Dispatch synchronous agent functions without blocking
    the event loop.
    """

    handler = AGENT_REGISTRY.get(request.receiver)

    if handler is None:
        raise ValueError(
            f"No registered handler for {request.receiver}"
        )

    loop = asyncio.get_running_loop()

    return await asyncio.wait_for(
        loop.run_in_executor(
            None,
            partial(handler, request, incident),
        ),
        timeout=timeout_seconds,
    )
