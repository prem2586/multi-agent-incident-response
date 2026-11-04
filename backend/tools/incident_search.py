
import json
import re
from pathlib import Path
from typing import Any

from backend.models.incident import Incident


ROOT = Path(__file__).resolve().parents[2]
KB_DIR = ROOT / "data" / "knowledge_base"

STOPWORDS = {
    "the", "and", "for", "with", "from", "after",
    "before", "were", "was", "are", "this", "that",
    "service", "detected", "increased", "high",
    "error", "errors", "application", "due", "http",
    "api", "completed", "successfully", "recent",
}


def tokenize(text: str) -> set[str]:
    """Normalize text into searchable tokens."""
    tokens = set(
        re.findall(r"[a-z0-9]+", text.lower())
    )
    return {
        token for token in tokens
        if len(token) > 2 and token not in STOPWORDS
    }


def load_json(filename: str) -> list[dict[str, Any]]:
    path = KB_DIR / filename

    with path.open(encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        raise ValueError(
            f"{filename} must contain a JSON array"
        )

    return data


def build_query_tokens(incident: Incident) -> set[str]:
    """
    Build retrieval query from observed evidence.

    Do not use metadata.suspected_cause or root_cause.
    """
    texts = [
        incident.title,
        incident.description,
        *incident.affected_services,
    ]

    for log in incident.logs:
        texts.append(log.message)

    for metric in incident.metrics:
        texts.append(metric.name.replace("_", " "))

    return tokenize(" ".join(texts))


def search_past_incidents(
    incident: Incident,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Rank historical incidents using observable signals."""

    historical = load_json("past_incidents.json")
    query_tokens = build_query_tokens(incident)

    matches = []

    for record in historical:
        symptom_tokens = tokenize(
            " ".join(record.get("symptoms", []))
        )

        keyword_tokens = tokenize(
            " ".join(record.get("keywords", []))
        )

        title_tokens = tokenize(
            record.get("title", "")
        )

        symptom_overlap = len(
            query_tokens & symptom_tokens
        )

        keyword_overlap = len(
            query_tokens & keyword_tokens
        )

        title_overlap = len(
            query_tokens & title_tokens
        )

        service_match = (
            record.get("service")
            in incident.affected_services
        )

        type_match = (
            record.get("incident_type")
            == incident.incident_type.value
        )

        score = (
            symptom_overlap * 3
            + keyword_overlap * 2
            + title_overlap
            + (4 if service_match else 0)
            + (2 if type_match else 0)
        )

        if score <= 0:
            continue

        matches.append({
            **record,
            "similarity_score": score,
            "matched_tokens": sorted(
                query_tokens
                & (
                    symptom_tokens
                    | keyword_tokens
                    | title_tokens
                )
            ),
        })

    matches.sort(
        key=lambda item: (
            -item["similarity_score"],
            item["incident_id"],
        )
    )

    return matches[:max(top_k, 0)]


def get_runbook(
    runbook_id: str,
) -> dict[str, Any] | None:
    """Retrieve a runbook by its identifier."""

    runbooks = load_json("runbooks.json")

    for runbook in runbooks:
        if runbook.get("runbook_id") == runbook_id:
            return runbook

    return None
