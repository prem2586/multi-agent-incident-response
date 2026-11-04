
from backend.models.incident import Incident
from backend.protocols.messages import (
    AgentResponse,
    AgentRole,
    MessageStatus,
)
from backend.tools.remediation_planner import (
    build_remediation_plan,
    build_planning_trace,
)


def make_response(
    role: AgentRole,
    status: MessageStatus,
    findings=None,
    confidence=0.8,
):
    return AgentResponse(
        request_message_id="test-request",
        incident_id="INC-001",
        correlation_id="test-correlation",
        sender=role,
        receiver=AgentRole.COORDINATOR,
        status=status,
        findings=findings or [],
        evidence=[],
        confidence=confidence,
        missing_information=[],
        metadata={},
    )


def test_knowledge_failure_removes_risky_actions():
    incident = Incident(
        incident_id="INC-001",
        title="Checkout degradation",
        description="Database connection pool exhaustion",
        incident_type="service_degradation",
        severity="high",
    )

    observability = make_response(
        AgentRole.OBSERVABILITY,
        MessageStatus.COMPLETED,
        findings=[
            "Database connection pool exhaustion detected",
            "Recent deployment detected",
        ],
        confidence=1.0,
    )

    knowledge = make_response(
        AgentRole.KNOWLEDGE,
        MessageStatus.FAILED,
        confidence=0.0,
    )

    plan = build_remediation_plan(
        incident, observability, knowledge
    )

    action_types = [
        action.action_type for action in plan.actions
    ]

    assert "verify_database_connections" in action_types
    assert "rollback_deployment" not in action_types
    assert plan.execution_allowed is False

    trace = build_planning_trace(
        plan, observability, knowledge
    )

    assert trace["planning_strategy"] == (
        "telemetry_only_fallback"
    )


def test_observability_failure_collects_telemetry():
    incident = Incident(
        incident_id="INC-001",
        title="Checkout degradation",
        description="Checkout service errors",
        incident_type="service_degradation",
        severity="high",
    )

    observability = make_response(
        AgentRole.OBSERVABILITY,
        MessageStatus.FAILED,
        confidence=0.0,
    )

    knowledge = make_response(
        AgentRole.KNOWLEDGE,
        MessageStatus.COMPLETED,
        findings=["Similar incident found"],
        confidence=0.7,
    )

    plan = build_remediation_plan(
        incident, observability, knowledge
    )

    assert len(plan.actions) == 1
    assert plan.actions[0].action_type == (
        "collect_more_telemetry"
    )
    assert plan.confidence == 0.0


def test_normal_plan_keeps_action_dependencies():
    incident = Incident(
        incident_id="INC-001",
        title="Checkout degradation",
        description="Database connection pool exhaustion",
        incident_type="service_degradation",
        severity="high",
    )

    observability = make_response(
        AgentRole.OBSERVABILITY,
        MessageStatus.COMPLETED,
        findings=[
            "Database connection pool exhaustion detected",
            "Recent deployment detected",
        ],
        confidence=1.0,
    )

    knowledge = make_response(
        AgentRole.KNOWLEDGE,
        MessageStatus.COMPLETED,
        confidence=0.8,
    )

    plan = build_remediation_plan(
        incident, observability, knowledge
    )

    assert len(plan.actions) == 2
    assert plan.actions[0].action_id == "ACT-001"
    assert plan.actions[1].prerequisites == ["ACT-001"]
    assert plan.requires_human_approval is True
    assert plan.execution_allowed is False
