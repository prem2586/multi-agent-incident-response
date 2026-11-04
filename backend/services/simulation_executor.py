
from datetime import datetime, timezone

from backend.models.remediation import RemediationPlan


ALLOWED_ACTIONS = {
    "verify_database_connections",
    "rollback_deployment",
    "restart_service",
    "inspect_cpu",
    "review_authentication_activity",
    "enable_rate_limiting",
    "collect_more_telemetry",
}


def execute_simulated_plan(
    plan: RemediationPlan,
    approved: bool,
) -> list[dict]:
    """Execute only simulated, explicitly approved actions."""

    if not approved:
        raise PermissionError("Human approval required")

    if not plan.requires_human_approval:
        raise ValueError("Invalid plan: approval policy missing")

    actions = sorted(plan.actions, key=lambda a: a.priority)
    completed_ids = set()
    results = []

    # Validate the entire plan before executing any action.
    action_ids = [action.action_id for action in actions]

    if len(action_ids) != len(set(action_ids)):
        raise ValueError("Duplicate action IDs")

    for action in actions:
        if not action.requires_approval:
            raise ValueError("Action missing approval requirement")

        if action.action_type not in ALLOWED_ACTIONS:
            raise ValueError(
                f"Unsupported simulated action: {action.action_type}"
            )

        for dependency in action.prerequisites:
            if dependency not in action_ids:
                raise ValueError(
                    f"Missing prerequisite: {dependency}"
                )

    for action in actions:
        if not set(action.prerequisites).issubset(completed_ids):
            raise ValueError(
                f"Prerequisites not completed for {action.action_id}"
            )

        results.append({
            "action_id": action.action_id,
            "action_type": action.action_type,
            "status": "simulated_success",
            "description": action.description,
            "executed_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "simulation_only": True,
        })

        completed_ids.add(action.action_id)

    return results
