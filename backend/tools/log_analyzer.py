
from collections import Counter
from datetime import datetime
from typing import Any

from backend.models.incident import Incident, LogEntry


def analyze_logs(incident: Incident) -> dict[str, Any]:
    """Analyze incident logs using deterministic rules."""

    logs = sorted(incident.logs, key=lambda log: log.timestamp)

    if not logs:
        return {
            "findings": [],
            "evidence": [],
            "missing_information": ["No logs available"],
            "error_count": 0,
            "warning_count": 0,
            "deployment_detected": False,
        }

    findings = []
    evidence = []
    missing_information = []

    error_logs = [
        log for log in logs
        if log.level.upper() == "ERROR"
    ]

    warning_logs = [
        log for log in logs
        if log.level.upper() in ("WARN", "WARNING")
    ]

    error_count = len(error_logs)
    warning_count = len(warning_logs)

    if error_count:
        findings.append(
            f"Detected {error_count} error log entries"
        )

    if warning_count:
        findings.append(
            f"Detected {warning_count} warning log entries"
        )

    error_patterns = Counter(
        log.message for log in error_logs
    )

    for message, count in error_patterns.items():
        evidence.append({
            "source": "application_logs",
            "description": message,
            "value": count,
        })

    deployment_logs = [
        log for log in logs
        if "deployment" in log.message.lower()
    ]

    deployment_detected = bool(deployment_logs)

    for log in deployment_logs:
        version = log.metadata.get("version", "unknown")

        findings.append(
            f"Deployment version {version} detected"
        )

        evidence.append({
            "source": "deployment_logs",
            "description": log.message,
            "value": version,
        })

    pool_errors = [
        log for log in logs
        if "connection pool" in log.message.lower()
        and (
            "exhaust" in log.message.lower()
            or "timeout" in log.message.lower()
        )
    ]

    if pool_errors:
        findings.append(
            "Database connection pool exhaustion detected in logs"
        )

        evidence.append({
            "source": "application_logs",
            "description": "Database connection pool errors",
            "value": len(pool_errors),
        })

    http_errors = [
        log for log in logs
        if "HTTP 5" in log.message.upper()
        or "service unavailable" in log.message.lower()
    ]

    if http_errors:
        findings.append(
            "HTTP 5xx service errors detected"
        )

    # Check whether the deployment preceded the first error.
    if deployment_logs and error_logs:
        first_deployment = min(
            log.timestamp for log in deployment_logs
        )
        first_error = min(
            log.timestamp for log in error_logs
        )

        if first_deployment <= first_error:
            findings.append(
                "Deployment occurred before the first recorded error"
            )
            evidence.append({
                "source": "log_timeline",
                "description": "Deployment preceded application errors",
                "value": {
                    "deployment_time": first_deployment.isoformat(),
                    "first_error_time": first_error.isoformat(),
                },
            })

    return {
        "findings": findings,
        "evidence": evidence,
        "missing_information": missing_information,
        "error_count": error_count,
        "warning_count": warning_count,
        "deployment_detected": deployment_detected,
    }
