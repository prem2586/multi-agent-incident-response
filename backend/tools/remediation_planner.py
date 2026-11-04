
from backend.models.incident import Incident
from backend.models.remediation import (
    RemediationAction,
    RemediationPlan,
    RiskLevel,
)
from backend.protocols.messages import (
    AgentResponse,
    MessageStatus,
)


DIAGNOSTIC_ACTIONS = {
    "verify_database_connections",
    "inspect_cpu",
    "review_authentication_activity",
    "collect_more_telemetry",
}


def build_remediation_plan(
    incident: Incident,
    observability: AgentResponse,
    knowledge: AgentResponse,
) -> RemediationPlan:
    """Build an evidence-based plan with failure-aware fallback."""

    findings_text = " ".join(observability.findings).lower()
    runbooks = knowledge.metadata.get("retrieved_runbooks", [])

    actions = []
    missing_information = list(dict.fromkeys(
        observability.missing_information
        + knowledge.missing_information
    ))

    observability_failed = (
        observability.status == MessageStatus.FAILED
    )
    knowledge_failed = (
        knowledge.status == MessageStatus.FAILED
    )

    pool_evidence = (
        "connection pool" in findings_text
        and (
            "exhaustion" in findings_text
            or "saturation" in findings_text
        )
    )

    deployment_evidence = "deployment" in findings_text
    cpu_evidence = "high cpu utilization" in findings_text

    security_evidence = (
        incident.incident_type.value == "security_alert"
        and any(
            term in findings_text
            for term in ("authentication", "login", "suspicious")
        )
    )

    # STEP 1: Select hypothesis and generate candidate actions.

    if pool_evidence:
        hypothesis = (
            "Database connection pool exhaustion "
            "is contributing to service degradation"
        )

        actions.append(
            RemediationAction(
                action_id="ACT-001",
                action_type="verify_database_connections",
                description=(
                    "Inspect active and idle database connections "
                    "and acquisition timeouts"
                ),
                priority=1,
                risk=RiskLevel.LOW,
                prerequisites=[],
                rollback_plan=(
                    "No rollback needed; read-only diagnostic"
                ),
                rationale=(
                    "Telemetry indicates database "
                    "connection pool saturation"
                ),
                evidence_sources=["observability_agent"],
            )
        )

        if deployment_evidence:
            actions.append(
                RemediationAction(
                    action_id="ACT-002",
                    action_type="rollback_deployment",
                    description=(
                        "Simulate rollback to the previous "
                        "stable application version"
                    ),
                    priority=2,
                    risk=RiskLevel.MEDIUM,
                    prerequisites=["ACT-001"],
                    rollback_plan=(
                        "Restore the current version if "
                        "rollback causes additional issues"
                    ),
                    rationale=(
                        "Deployment preceded observed "
                        "database connection errors"
                    ),
                    evidence_sources=[
                        "observability_agent",
                        "knowledge_agent",
                    ],
                )
            )

    elif cpu_evidence:
        hypothesis = (
            "CPU saturation may be contributing "
            "to elevated service latency"
        )

        actions.append(
            RemediationAction(
                action_id="ACT-001",
                action_type="inspect_cpu",
                description=(
                    "Inspect CPU utilization and thread activity"
                ),
                priority=1,
                risk=RiskLevel.LOW,
                prerequisites=[],
                rollback_plan=(
                    "No rollback needed; read-only diagnostic"
                ),
                rationale="High CPU utilization observed",
                evidence_sources=["observability_agent"],
            )
        )

    elif security_evidence:
        hypothesis = (
            "Suspicious authentication activity "
            "may indicate an automated attack"
        )

        actions.extend([
            RemediationAction(
                action_id="ACT-001",
                action_type="review_authentication_activity",
                description=(
                    "Review authentication failures "
                    "and suspicious source activity"
                ),
                priority=1,
                risk=RiskLevel.LOW,
                prerequisites=[],
                rollback_plan=(
                    "No rollback needed; read-only diagnostic"
                ),
                rationale="Authentication anomalies detected",
                evidence_sources=["observability_agent"],
            ),
            RemediationAction(
                action_id="ACT-002",
                action_type="enable_rate_limiting",
                description=(
                    "Simulate enabling controlled "
                    "authentication rate limiting"
                ),
                priority=2,
                risk=RiskLevel.MEDIUM,
                prerequisites=["ACT-001"],
                rollback_plan=(
                    "Restore previous rate-limiting policy"
                ),
                rationale=(
                    "Reduce suspicious automated traffic"
                ),
                evidence_sources=[
                    "observability_agent",
                    "knowledge_agent",
                ],
            ),
        ])

    else:
        hypothesis = (
            "Insufficient evidence to determine "
            "a reliable root cause"
        )

        missing_information.append(
            "Additional diagnostic evidence required"
        )

        actions.append(
            _collect_telemetry_action(
                "Current evidence is insufficient"
            )
        )

    # STEP 2: Adapt the plan to agent failures.

    if knowledge_failed:
        missing_information.append(
            "Historical evidence unavailable"
        )

        # Keep only diagnostic actions.
        actions = [
            action for action in actions
            if action.action_type in DIAGNOSTIC_ACTIONS
        ]

    if observability_failed:
        missing_information.append(
            "Live telemetry analysis unavailable"
        )

        # Telemetry is essential for root-cause diagnosis.
        hypothesis = (
            "Insufficient live telemetry to determine root cause"
        )

        actions = [
            _collect_telemetry_action(
                "Observability Agent unavailable"
            )
        ]

    # STEP 3: Attach available runbook references.

    runbook_ids = [
        str(runbook["runbook_id"])
        for runbook in runbooks
        if isinstance(runbook, dict)
        and runbook.get("runbook_id")
    ]

    if not knowledge_failed and runbook_ids:
        for action in actions:
            if "knowledge_agent" in action.evidence_sources:
                action.rationale += (
                    "; relevant runbooks: "
                    + ", ".join(dict.fromkeys(runbook_ids))
                )

    # STEP 4: Calculate conservative confidence.

    confidence = round(
        min(
            observability.confidence,
            knowledge.confidence,
        ),
        2,
    )

    if observability_failed:
        confidence = 0.0

    # STEP 5: Validate dependencies after fallback filtering.

    action_ids = {action.action_id for action in actions}

    for action in actions:
        for dependency in action.prerequisites:
            if dependency not in action_ids:
                raise ValueError(
                    f"Action {action.action_id} has missing "
                    f"prerequisite {dependency}"
                )
    # STEP 6: Return a plan that cannot execute automatically.

    return RemediationPlan(
        incident_id=incident.incident_id,
        root_cause_hypothesis=hypothesis,
        confidence=confidence,
        actions=sorted(
            actions,
            key=lambda action: action.priority,
        ),
        missing_information=list(dict.fromkeys(
            missing_information
        )),
        requires_human_approval=True,
        execution_allowed=False,
    )


def _collect_telemetry_action(reason: str) -> RemediationAction:
    return RemediationAction(
        action_id="ACT-001",
        action_type="collect_more_telemetry",
        description=(
            "Collect additional logs, metrics, "
            "and dependency health information"
        ),
        priority=1,
        risk=RiskLevel.LOW,
        prerequisites=[],
        rollback_plan="No rollback needed",
        rationale=reason,
        evidence_sources=["observability_agent"],
    )


def build_planning_trace(
    plan: RemediationPlan,
    observability: AgentResponse,
    knowledge: AgentResponse,
) -> dict:
    """Produce an inspectable explanation of the selected plan."""

    observability_failed = (
        observability.status == MessageStatus.FAILED
    )
    knowledge_failed = (
        knowledge.status == MessageStatus.FAILED
    )

    if observability_failed:
        strategy = "telemetry_collection_fallback"
    elif knowledge_failed:
        strategy = "telemetry_only_fallback"
    else:
        strategy = "evidence_conditioned_hierarchical"

    return {
        "planning_strategy": strategy,
        "goal": "Investigate and safely remediate the incident",
        "root_cause_hypothesis": plan.root_cause_hypothesis,
        "agent_status": {
            "observability": observability.status.value,
            "knowledge": knowledge.status.value,
        },
        "task_hierarchy": [
            {
                "action_id": action.action_id,
                "action_type": action.action_type,
                "priority": action.priority,
                "risk": action.risk.value,
                "prerequisites": action.prerequisites,
                "rationale": action.rationale,
                "evidence_sources": action.evidence_sources,
            }
            for action in plan.actions
        ],
        "missing_information": plan.missing_information,
        "confidence": plan.confidence,
        "requires_human_approval": True,
        "execution_allowed": False,
    }
