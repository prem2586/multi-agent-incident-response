
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import json
import re



def as_dict(value: Any) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return {}


def safe_text(value: Any) -> str:
    if value is None:
        return "Not available"
    if isinstance(value, (dict, list)):
        return json.dumps(value, default=str)
    return str(value).replace("\n", " ").replace("\r", " ")


def bullet_items(items: Any) -> str:
    if not items:
        return "- Not available"

    if not isinstance(items, list):
        items = [items]

    return "\n".join(
        f"- {safe_text(item)}"
        for item in items
    )


def get_agent_response(responses: dict, role: str) -> dict:
    if not isinstance(responses, dict):
        return {}

    for key, value in responses.items():
        role_name = str(
            getattr(key, "value", key)
        ).lower()

        normalized = role_name.replace("_agent", "")

        if normalized == role.lower():
            return as_dict(value)

    return {}



def generate_postmortem(
    incident: Any,
    coordinator_result: Any,
    workflow_state: dict,
) -> str:
    incident = as_dict(incident)
    coordinator = as_dict(coordinator_result)
    state = as_dict(workflow_state)

    responses = coordinator.get("agent_responses", {})
    print("[POSTMORTEM] Coordinator keys:", list(coordinator.keys()))
    print("[POSTMORTEM] Agent response keys:", list(responses.keys()))

    observability = get_agent_response(
        responses, "observability"
    )
    knowledge = get_agent_response(
        responses, "knowledge"
    )
    remediation = get_agent_response(
        responses, "remediation"
    )

    plan = as_dict(
        coordinator.get("remediation_plan")
        or state.get("remediation_plan")
    )

    actions = plan.get("actions", [])
    if not isinstance(actions, list):
        actions = []

    action_lines = []
    for action in actions:
        action = as_dict(action)
        action_lines.append(
            "- **{id}** — {action_type}\n"
            "  - Risk: {risk}\n"
            "  - Prerequisites: {deps}\n"
            "  - Rationale: {rationale}".format(
                id=safe_text(action.get("action_id")),
                action_type=safe_text(
                    action.get("action_type")
                ),
                risk=safe_text(
                    action.get("risk")
                    or action.get("risk_level")
                ),
                deps=safe_text(
                    action.get("prerequisites", [])
                ),
                rationale=safe_text(
                    action.get("rationale")
                ),
            )
        )

    approval = (
        state.get("approval_decision")
        or state.get("decision")
        or "Not recorded"
    )

    execution_results = (
        state.get("execution_results") or []
    )

    if isinstance(execution_results, dict):
        execution_results = [execution_results]

    generated_at = datetime.now(
        timezone.utc
    ).isoformat()

    if str(approval).lower() in ("reject", "rejected"):
        execution_summary = (
            "Remediation was rejected by the operator. "
            "No actions were executed."
        )
    else:
        execution_summary = format_execution_results(
            execution_results
        )

    return f"""# Incident Post-Mortem

## 1. Incident Overview

- **Incident ID:** {safe_text(incident.get("incident_id"))}
- **Title:** {safe_text(incident.get("title"))}
- **Severity:** {safe_text(incident.get("severity"))}
- **Incident Type:** {safe_text(incident.get("incident_type"))}
- **Generated At (UTC):** {generated_at}
- **Workflow Status:** {safe_text(state.get("status"))}

### Description

{safe_text(incident.get("description"))}

## 2. Investigation Findings

### Observability Agent

**Status:** {safe_text(observability.get("status"))}

{bullet_items(observability.get("findings", []))}

### Knowledge Agent

**Status:** {safe_text(knowledge.get("status"))}

{bullet_items(knowledge.get("findings", []))}

### Remediation Agent

**Status:** {safe_text(remediation.get("status"))}

{bullet_items(remediation.get("findings", []))}

## 3. Probable Root Cause

{safe_text(
    incident.get("root_cause")
    or plan.get("root_cause_hypothesis")
)}

This is an evidence-based hypothesis, not a
confirmed production root cause.

## 4. Proposed Remediation Plan

{chr(10).join(action_lines) if action_lines else "- No actions proposed"}

## 5. Human Approval

- **Decision:** {safe_text(approval)}
- **Human approval required:** {safe_text(plan.get("requires_human_approval"))}

## 6. Simulated Execution Results

{execution_summary}

All reported execution outcomes are simulated.
No actual production remediation is implied.

## 7. Missing Information and Limitations

{bullet_items(
    coordinator.get("missing_information")
    or plan.get("missing_information")
    or []
)}

## 8. Follow-Up Actions

- Review unresolved telemetry gaps.
- Validate the root-cause hypothesis.
- Review the remediation plan and its prerequisites.
- Improve monitoring and alert thresholds.
- Update incident runbooks where appropriate.

## 9. Conclusion

This report summarizes the available investigation
evidence, remediation proposal, human decision,
and simulated outcome.

It is a draft intended for operator review.
"""
    

def save_postmortem(
    incident_id: str,
    report: str,
    output_dir: str = "data/postmortems",
) -> Path:
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)

    safe_id = re.sub(
        r"[^A-Za-z0-9_-]",
        "_",
        incident_id,
    )

    if not safe_id:
        raise ValueError("Invalid incident ID")

    timestamp = datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%S%fZ")

    path = directory / (
        f"{safe_id}_{timestamp}.md"
    )

    path.write_text(report, encoding="utf-8")
    return path

def format_execution_results(results: list) -> str:
    if not results:
        return "- No simulated execution results."

    lines = []

    for item in results:
        action = as_dict(item)

        lines.append(
            f"- **{safe_text(action.get('action_id'))}** "
            f"— {safe_text(action.get('action_type'))}\n"
            f"  - Status: {safe_text(action.get('status'))}\n"
            f"  - Description: {safe_text(action.get('description'))}\n"
            f"  - Simulation only: {safe_text(action.get('simulation_only'))}"
        )

    return "\n".join(lines)