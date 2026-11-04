
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
from backend.tools.log_analyzer import analyze_logs
from backend.tools.metrics_analyzer import analyze_metrics

@traceable(name="Observability Agent", run_type="chain")
def run_observability_agent(
    request: AgentRequest,
    incident: Incident,
) -> AgentResponse:
    """Analyze incident telemetry and return a structured response."""

    if request.receiver != AgentRole.OBSERVABILITY:
        raise ValueError(
            "Request is not addressed to the Observability Agent"
        )

    if request.task != AgentTask.ANALYZE_TELEMETRY:
        raise ValueError(
            f"Unsupported task: {request.task}"
        )

    if request.incident_id != incident.incident_id:
        raise ValueError(
            "Request incident ID does not match incident data"
        )

    try:
        log_result = analyze_logs(incident)
        metrics_result = analyze_metrics(incident)

        findings = (
            log_result["findings"]
            + metrics_result["findings"]
        )

        raw_evidence = (
            log_result["evidence"]
            + metrics_result["evidence"]
        )

        evidence = [
            Evidence.model_validate(item)
            for item in raw_evidence
        ]

        missing_information = list(dict.fromkeys(
            log_result["missing_information"]
            + metrics_result["missing_information"]
        ))

        values = metrics_result["values"]

        pool_saturated = (
            values["db_pool_percent"] is not None
            and values["db_pool_percent"] > 90
        )

        pool_log_detected = any(
            "connection pool exhaustion" in finding.lower()
            for finding in findings
        )

        deployment_detected = log_result[
            "deployment_detected"
        ]

        if pool_saturated and pool_log_detected:
            findings.append(
                "Root cause hypothesis: database connection "
                "pool exhaustion is contributing to the incident"
            )

            if deployment_detected:
                findings.append(
                    "Recent deployment may be associated "
                    "with the connection pool issue; "
                    "causality is not yet confirmed"
                )

            next_action = (
                "Compare deployment changes with historical "
                "incidents and database connection configuration"
            )

        elif values["error_rate_percent"] is not None:
            next_action = (
                "Investigate application errors and correlate "
                "them with deployment and infrastructure events"
            )

        else:
            next_action = (
                "Collect additional telemetry before "
                "determining the root cause"
            )

        # Simple evidence coverage score for this simulation.
        # This is not a calibrated probability.
        available_signals = sum([
            bool(incident.logs),
            values["latency_ms"] is not None,
            values["error_rate_percent"] is not None,
            values["db_pool_percent"] is not None,
            values["cpu_percent"] is not None,
        ])

        confidence = round(
            available_signals / 5,
            2
        )

        if not findings:
            confidence = 0.0

        status = (
            MessageStatus.PARTIAL
            if missing_information
            else MessageStatus.COMPLETED
        )

        return AgentResponse(
            request_message_id=request.message_id,
            incident_id=incident.incident_id,
            correlation_id=request.correlation_id,
            sender=AgentRole.OBSERVABILITY,
            receiver=request.sender,
            status=status,
            findings=findings,
            evidence=evidence,
            confidence=confidence,
            missing_information=missing_information,
            recommended_next_action=next_action,
            metadata={
                "log_error_count": log_result["error_count"],
                "log_warning_count": log_result["warning_count"],
                "metrics_analyzed": metrics_result["metric_count"],
                "confidence_method": "telemetry_coverage",
            },
        )

    except Exception as exc:
        return AgentResponse(
            request_message_id=request.message_id,
            incident_id=incident.incident_id,
            correlation_id=request.correlation_id,
            sender=AgentRole.OBSERVABILITY,
            receiver=request.sender,
            status=MessageStatus.FAILED,
            confidence=0.0,
            error=str(exc),
            recommended_next_action=(
                "Retry telemetry analysis or escalate "
                "to manual investigation"
            ),
        )
