
from typing import Any

from backend.models.incident import Incident


LATENCY_THRESHOLD_MS = 1000
ERROR_RATE_THRESHOLD_PERCENT = 5.0
DB_POOL_THRESHOLD_PERCENT = 90.0
CPU_THRESHOLD_PERCENT = 85.0


def analyze_metrics(incident: Incident) -> dict[str, Any]:
    """Analyze incident metrics using deterministic thresholds."""

    findings = []
    evidence = []
    missing_information = []

    # Latest observation wins when metrics repeat.
    latest_metrics = {}

    for metric in sorted(
        incident.metrics,
        key=lambda m: m.timestamp
    ):
        latest_metrics[metric.name] = metric

    def get_metric(name: str):
        metric = latest_metrics.get(name)
        return metric.value if metric else None

    latency = get_metric("api_latency_p95")
    baseline_latency = get_metric("api_latency_baseline_p95")
    error_rate = get_metric("http_5xx_error_rate")
    db_pool = get_metric("db_connection_pool_utilization")
    cpu = get_metric("cpu_utilization")

    if latency is None:
        missing_information.append(
            "API p95 latency metric unavailable"
        )
    elif latency > LATENCY_THRESHOLD_MS:
        findings.append(
            f"High API p95 latency detected: {latency:.0f} ms"
        )
        evidence.append({
            "source": "metrics",
            "description": "API p95 latency exceeds threshold",
            "value": latency,
        })

    if latency is not None and baseline_latency is not None:
        if baseline_latency > 0:
            increase = latency / baseline_latency

            if increase >= 2:
                findings.append(
                    f"API latency increased {increase:.1f}x "
                    f"from baseline ({baseline_latency:.0f} ms "
                    f"to {latency:.0f} ms)"
                )
                evidence.append({
                    "source": "metrics",
                    "description": "Latency increase relative to baseline",
                    "value": increase,
                })
    elif baseline_latency is None:
        missing_information.append(
            "Baseline API latency metric unavailable"
        )

    if error_rate is None:
        missing_information.append(
            "HTTP 5xx error rate metric unavailable"
        )
    elif error_rate > ERROR_RATE_THRESHOLD_PERCENT:
        findings.append(
            f"Elevated HTTP 5xx error rate: {error_rate:.1f}%"
        )
        evidence.append({
            "source": "metrics",
            "description": "HTTP 5xx error rate exceeds threshold",
            "value": error_rate,
        })

    if db_pool is None:
        missing_information.append(
            "Database connection pool utilization unavailable"
        )
    elif db_pool > DB_POOL_THRESHOLD_PERCENT:
        findings.append(
            f"Database connection pool saturation: {db_pool:.0f}%"
        )
        evidence.append({
            "source": "metrics",
            "description": "Database pool utilization exceeds threshold",
            "value": db_pool,
        })

    if cpu is None:
        missing_information.append(
            "CPU utilization metric unavailable"
        )
    elif cpu > CPU_THRESHOLD_PERCENT:
        findings.append(
            f"High CPU utilization: {cpu:.0f}%"
        )
        evidence.append({
            "source": "metrics",
            "description": "CPU utilization exceeds threshold",
            "value": cpu,
        })

    return {
        "findings": findings,
        "evidence": evidence,
        "missing_information": missing_information,
        "metric_count": len(latest_metrics),
        "values": {
            "latency_ms": latency,
            "baseline_latency_ms": baseline_latency,
            "error_rate_percent": error_rate,
            "db_pool_percent": db_pool,
            "cpu_percent": cpu,
        },
    }
