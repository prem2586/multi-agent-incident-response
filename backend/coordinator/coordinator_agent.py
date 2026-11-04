
import asyncio
import os
import logging

from uuid import uuid4

from langsmith import traceable

from backend.models.incident import Incident
from backend.protocols.messages import (
    AgentRole,
    AgentTask,
    AgentResponse,
    MessageStatus,
)
from backend.coordinator.state import CoordinatorResult
from backend.coordinator.handoff import (
    create_agent_request,
    dispatch_agent,
)

from backend.agents.remediation_llm import enhance_remediation_plan
from backend.models.remediation import RemediationPlan


logger = logging.getLogger(__name__)

class IncidentCoordinator:

    def __init__(self, timeout_seconds: float = 15.0):
        self.timeout_seconds = timeout_seconds

    @traceable(
        name="Incident Coordinator",
        run_type="chain",
    )    
    async def investigate(
        self,
        incident: Incident,
    ) -> CoordinatorResult:

        correlation_id = str(uuid4())
        errors = []
        missing_information = []

        obs_request = create_agent_request(
            incident_id=incident.incident_id,
            correlation_id=correlation_id,
            receiver=AgentRole.OBSERVABILITY,
            task=AgentTask.ANALYZE_TELEMETRY,
        )

        knowledge_request = create_agent_request(
            incident_id=incident.incident_id,
            correlation_id=correlation_id,
            receiver=AgentRole.KNOWLEDGE,
            task=AgentTask.SEARCH_PAST_INCIDENTS,
            payload={"top_k": 3},
        )

        # Parallel diagnosis.
        results = await asyncio.gather(
            dispatch_agent(
                obs_request,
                incident,
                self.timeout_seconds,
            ),
            dispatch_agent(
                knowledge_request,
                incident,
                self.timeout_seconds,
            ),
            return_exceptions=True,
        )

        responses = {}

        for role, request, result in zip(
            [AgentRole.OBSERVABILITY, AgentRole.KNOWLEDGE],
            [obs_request, knowledge_request],
            results,
        ):
            if isinstance(result, BaseException):
                errors.append(
                    f"{role.value} failed: {result}"
                )

                responses[role.value] = AgentResponse(
                    request_message_id=request.message_id,
                    incident_id=incident.incident_id,
                    correlation_id=correlation_id,
                    sender=role,
                    receiver=AgentRole.COORDINATOR,
                    status=MessageStatus.FAILED,
                    confidence=0.0,
                    error=str(result),
                    missing_information=[
                        f"{role.value} result unavailable"
                    ],
                )
            else:
                responses[role.value] = result

                if result.status == MessageStatus.FAILED:
                    errors.append(
                        f"{role.value}: {result.error}"
                    )

                missing_information.extend(
                    result.missing_information
                )

        obs_response = responses[AgentRole.OBSERVABILITY.value]
        knowledge_response = responses[AgentRole.KNOWLEDGE.value]

        remediation_request = create_agent_request(
            incident_id=incident.incident_id,
            correlation_id=correlation_id,
            receiver=AgentRole.REMEDIATION,
            task=AgentTask.GENERATE_REMEDIATION,
            payload={
                "observability": obs_response.model_dump(
                    mode="json"
                ),
                "knowledge": knowledge_response.model_dump(
                    mode="json"
                ),
            },
        )

        try:
            remediation_response = await dispatch_agent(
                remediation_request,
                incident,
                self.timeout_seconds,
            )
        except Exception as exc:
            remediation_response = AgentResponse(
                request_message_id=remediation_request.message_id,
                incident_id=incident.incident_id,
                correlation_id=correlation_id,
                sender=AgentRole.REMEDIATION,
                receiver=AgentRole.COORDINATOR,
                status=MessageStatus.FAILED,
                confidence=0.0,
                error=str(exc),
            )

        responses[AgentRole.REMEDIATION.value] = remediation_response

        if remediation_response.status == MessageStatus.FAILED:
            errors.append(
                f"remediation_agent: {remediation_response.error}"
            )

        missing_information.extend(
            remediation_response.missing_information
        )

        # Retrieve deterministic remediation plan.
        plan = dict(
            remediation_response.metadata.get(
                "remediation_plan"
            ) or {}
        )

        planning_trace = remediation_response.metadata.get(
            "planning_trace", {}
        )

        # Enforce the safety invariant before LLM processing.
        plan["execution_allowed"] = False

        # Optional LLM reasoning:
        # LLM_PROVIDER=none   -> deterministic only
        # LLM_PROVIDER=claude -> Claude-assisted reasoning
        #
        # Only enhance an existing valid-looking plan.
        # Do not generate remediation actions when the
        # deterministic planner returned none.
        
        planning_mode = os.getenv(
            "PLANNING_MODE", "deterministic"
        ).strip().lower()

        logger.info(
            "Incident %s: planning mode=%s",
            incident.incident_id,
            planning_mode,
        )

        if planning_mode == "llm" and plan.get("actions"):

            logger.info(
                "Incident %s: invoking LLM enhancement",
                incident.incident_id,
            )

            plan = await enhance_remediation_plan(
                incident=incident.model_dump(mode="json"),
                observability=obs_response.model_dump(mode="json"),
                knowledge=knowledge_response.model_dump(mode="json"),
                deterministic_plan=plan,
            )

        elif planning_mode == "deterministic":
            logger.info(
                "Incident %s: deterministic mode; LLM skipped",
                incident.incident_id,
            )

        else:
            logger.warning(
                "Incident %s: LLM not invoked; "
                "mode=%s, actions_present=%s",
                incident.incident_id,
                planning_mode,
                bool(plan.get("actions")),
            )

        # Preserve coordinator safety invariant.
        plan["execution_allowed"] = False

        # Validate the plan using the existing schema.
        # If the LLM introduced incompatible fields,
        # fall back to the deterministic plan instead.

        try:
            plan = RemediationPlan.model_validate(
                plan
            ).model_dump(mode="json")
        except Exception:
            logger.exception(
                "Incident %s: remediation plan validation failed; "
                "falling back to deterministic plan",
                incident.incident_id,
            )
            # A validation failure should not authorize
            # execution or bypass human approval.
            plan = dict(
                remediation_response.metadata.get(
                    "remediation_plan"
                ) or {}
            )
            plan["execution_allowed"] = False

        if errors:
            status = "partial_failure"
        elif missing_information:
            status = "partial"
        else:
            status = "awaiting_approval"

        return CoordinatorResult(
            incident_id=incident.incident_id,
            correlation_id=correlation_id,
            status=status,
            root_cause_hypothesis=plan.get(
                "root_cause_hypothesis"
            ),
            agent_responses=responses,
            remediation_plan=plan,
            missing_information=list(dict.fromkeys(
                missing_information
            )),
            errors=errors,
            execution_allowed=False,
        )

@traceable(name="Incident Coordinator", run_type="chain")
async def run_coordinator(incident: Incident):
    coordinator = IncidentCoordinator()
    return await coordinator.investigate(incident)
