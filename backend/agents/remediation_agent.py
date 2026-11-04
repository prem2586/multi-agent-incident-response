
from langsmith import traceable

from backend.models.incident import Incident
from backend.protocols.messages import (
    AgentRequest,
    AgentResponse,
    AgentRole,
    AgentTask,
    Evidence,
    MessageStatus,
)
from backend.tools.remediation_planner import (
    build_remediation_plan,
    build_planning_trace,
)

from backend.agents.remediation_llm import (
    enhance_remediation_plan,
)

@traceable(name="Remediation Agent", run_type="chain")
def run_remediation_agent(
    request: AgentRequest,
    incident: Incident,
) -> AgentResponse:

    if request.receiver != AgentRole.REMEDIATION:
        raise ValueError(
            "Request is not addressed to the Remediation Agent"
        )

    if request.task != AgentTask.GENERATE_REMEDIATION:
        raise ValueError(
            f"Unsupported task: {request.task}"
        )

    if request.incident_id != incident.incident_id:
        raise ValueError(
            "Request incident ID does not match incident data"
        )

    try:
        observability = AgentResponse.model_validate(
            request.payload["observability"]
        )

        knowledge = AgentResponse.model_validate(
            request.payload["knowledge"]
        )

        plan = build_remediation_plan(
            incident=incident,
            observability=observability,
            knowledge=knowledge,
        )

        planning_trace = build_planning_trace(
            plan=plan,
            observability=observability,
            knowledge=knowledge,
        )

        findings = [
            f"Root cause hypothesis: "
            f"{plan.root_cause_hypothesis}"
        ]

        for action in plan.actions:
            findings.append(
                f"Priority {action.priority}: "
                f"{action.action_type} "
                f"(risk={action.risk.value})"
            )

        evidence = [
            Evidence(
                source="remediation_planner",
                description="Hierarchical remediation plan",
                value=plan.model_dump(mode="json"),
            )
        ]

        status = (
            MessageStatus.PARTIAL
            if plan.missing_information
            else MessageStatus.COMPLETED
        )

        return AgentResponse(
            request_message_id=request.message_id,
            incident_id=incident.incident_id,
            correlation_id=request.correlation_id,
            sender=AgentRole.REMEDIATION,
            receiver=request.sender,
            status=status,
            findings=findings,
            evidence=evidence,
            confidence=plan.confidence,
            missing_information=plan.missing_information,
            recommended_next_action=(
                "Submit remediation plan for human review; "
                "do not execute without approval"
            ),
            metadata={
                "remediation_plan": plan.model_dump(mode="json"),
                "planning_trace": planning_trace,
                "execution_allowed": False,
            },
        )

    except Exception as exc:
        return AgentResponse(
            request_message_id=request.message_id,
            incident_id=incident.incident_id,
            correlation_id=request.correlation_id,
            sender=AgentRole.REMEDIATION,
            receiver=request.sender,
            status=MessageStatus.FAILED,
            confidence=0.0,
            error=str(exc),
            recommended_next_action=(
                "Escalate to manual remediation planning"
            ),
        )
