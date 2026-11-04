
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
from backend.tools.incident_search import (
    get_runbook,
    search_past_incidents,
)

@traceable(name="Knowledge Agent", run_type="chain")
def run_knowledge_agent(
    request: AgentRequest,
    incident: Incident,
) -> AgentResponse:
    """Retrieve similar incidents and related runbooks."""

    if request.receiver != AgentRole.KNOWLEDGE:
        raise ValueError(
            "Request is not addressed to the Knowledge Agent"
        )

    if request.task != AgentTask.SEARCH_PAST_INCIDENTS:
        raise ValueError(
            f"Unsupported task: {request.task}"
        )

    if request.incident_id != incident.incident_id:
        raise ValueError(
            "Request incident ID does not match incident data"
        )
    # TEMPORARY: Simulate Knowledge Agent failure
    """     return AgentResponse(
        request_message_id=request.message_id,
        incident_id=incident.incident_id,
        correlation_id=request.correlation_id,
        sender=AgentRole.KNOWLEDGE,
        receiver=request.sender,
        status=MessageStatus.FAILED,
        confidence=0.0,
        findings=[],
        evidence=[],
        missing_information=[
            "Historical incident database unavailable"
        ],
        error="Simulated Knowledge Agent failure",
        recommended_next_action=(
            "Proceed with telemetry-only diagnosis"
        ),
    ) """

    try:
        top_k = int(request.payload.get("top_k", 3))
        top_k = max(1, min(top_k, 10))

        matches = search_past_incidents(
            incident=incident,
            top_k=top_k,
        )

        findings = []
        evidence = []
        missing_information = []
        retrieved_runbooks = []

        for match in matches:
            findings.append(
                f"Similar historical incident "
                f"{match['incident_id']}: {match['title']}"
            )

            findings.append(
                f"Historical root cause for "
                f"{match['incident_id']}: "
                f"{match['root_cause']}"
            )

            evidence.append(
                Evidence(
                    source=f"historical_incident:{match['incident_id']}",
                    description=(
                        "Historical incident match based on "
                        "observable symptoms and service context"
                    ),
                    value={
                        "similarity_score": match["similarity_score"],
                        "matched_tokens": match["matched_tokens"],
                        "resolution": match["resolution"],
                    },
                )
            )

            runbook_id = match.get("runbook_id")

            if runbook_id:
                runbook = get_runbook(runbook_id)

                if runbook:
                    if runbook_id not in [
                        item["runbook_id"]
                        for item in retrieved_runbooks
                    ]:
                        retrieved_runbooks.append(runbook)

                    findings.append(
                        f"Relevant runbook {runbook_id}: "
                        f"{runbook['title']}"
                    )
                else:
                    missing_information.append(
                        f"Runbook {runbook_id} unavailable"
                    )

        if not matches:
            missing_information.append(
                "No matching historical incidents found"
            )

            next_action = (
                "Continue investigation using live telemetry "
                "and collect additional diagnostic evidence"
            )

            confidence = 0.0
            status = MessageStatus.PARTIAL

        else:
            # Retrieval strength indicator, not a calibrated
            # probability of root-cause correctness.
            top_score = matches[0]["similarity_score"]
            confidence = round(
                top_score / (top_score + 10),
                2
            )

            next_action = (
                "Compare historical failure patterns with "
                "current telemetry before selecting remediation"
            )

            status = (
                MessageStatus.PARTIAL
                if missing_information
                else MessageStatus.COMPLETED
            )

        return AgentResponse(
            request_message_id=request.message_id,
            incident_id=incident.incident_id,
            correlation_id=request.correlation_id,
            sender=AgentRole.KNOWLEDGE,
            receiver=request.sender,
            status=status,
            findings=findings,
            evidence=evidence,
            confidence=confidence,
            missing_information=missing_information,
            recommended_next_action=next_action,
            metadata={
                "matched_incidents": [
                    {
                        "incident_id": match["incident_id"],
                        "title": match["title"],
                        "similarity_score": match["similarity_score"],
                        "runbook_id": match.get("runbook_id"),
                    }
                    for match in matches
                ],
                "retrieved_runbooks": retrieved_runbooks,
                "confidence_method": "lexical_retrieval_strength",
            },
        )

    except Exception as exc:
        return AgentResponse(
            request_message_id=request.message_id,
            incident_id=incident.incident_id,
            correlation_id=request.correlation_id,
            sender=AgentRole.KNOWLEDGE,
            receiver=request.sender,
            status=MessageStatus.FAILED,
            confidence=0.0,
            error=str(exc),
            recommended_next_action=(
                "Retry knowledge retrieval or proceed "
                "with telemetry-only diagnosis"
            ),
        )
