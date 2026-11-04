
import json
from pathlib import Path

from backend.models.incident import Incident


PROJECT_ROOT = Path(__file__).resolve().parents[2]
INCIDENT_DIR = PROJECT_ROOT / "data" / "incidents"

INCIDENT_FILES = {
    "INC-001": "service_degradation.json",
    "INC-002": "security_alert.json",
    "INC-003": "partial_telemetry.json",
}


def load_incident(incident_id: str) -> Incident:
    filename = INCIDENT_FILES.get(incident_id)

    if filename is None:
        raise ValueError(
            f"Unknown incident ID: {incident_id}"
        )

    path = INCIDENT_DIR / filename

    if not path.is_file():
        raise FileNotFoundError(
            f"Incident fixture not found: {filename}"
        )

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    incident = Incident.model_validate(data)

    if incident.incident_id != incident_id:
        raise ValueError(
            "Incident ID does not match fixture"
        )

    # Prevent evaluation ground truth from reaching agents.
    incident.metadata.pop("suspected_cause", None)

    return incident
