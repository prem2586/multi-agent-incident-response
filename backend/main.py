
import os
import secrets
from contextlib import asynccontextmanager
from typing import Literal

from dotenv import load_dotenv

# Load .env before importing application modules
load_dotenv()

from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.persistence.checkpointer import create_checkpointer
from backend.workflows.incident_graph import build_incident_graph
from backend.workflows.hitl import (
    set_graph,
    start_incident,
    resume_incident,
    get_incident_state,
)
from backend.services.incident_service import load_incident


API_KEY = os.getenv("INCIDENT_API_KEY")

if not API_KEY:
    raise RuntimeError(
        "Set INCIDENT_API_KEY before starting FastAPI"
    )


def require_api_key(
    x_api_key: str | None = Header(default=None),
):
    if not x_api_key or not secrets.compare_digest(
        x_api_key, API_KEY
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
        )


class CreateIncidentRequest(BaseModel):
    incident_id: str


class DecisionRequest(BaseModel):
    decision: Literal["approve", "reject"]
    approved_by: str = Field(default="", max_length=100)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize persistent SQLite checkpointer
    checkpointer, connection = await create_checkpointer()

    try:
        graph = build_incident_graph(checkpointer)
        set_graph(graph)

        yield

    finally:
        set_graph(None)
        await connection.close()


app = FastAPI(
    title="Multi-Agent Incident Response API",
    description="UCLA Agentic AI Capstone",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "incident-response-api",
    }


@app.post(
    "/incidents",
    dependencies=[Depends(require_api_key)],
)
async def create_incident(request: CreateIncidentRequest):
    try:
        incident = load_incident(request.incident_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    result = await start_incident(incident)

    return {
        "incident_id": incident.incident_id,
        "thread_id": result["thread_id"],
        "status": "awaiting_approval",
        "workflow": result["state"],
    }


@app.get(
    "/incidents/{thread_id}",
    dependencies=[Depends(require_api_key)],
)
async def get_incident(thread_id: str):
    try:
        snapshot = await get_incident_state(thread_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    if not snapshot["state"]:
        raise HTTPException(
            status_code=404,
            detail="Workflow not found",
        )

    return snapshot


@app.post(
    "/incidents/{thread_id}/decision",
    dependencies=[Depends(require_api_key)],
)
async def submit_decision(
    thread_id: str,
    request: DecisionRequest,
):
    if (
        request.decision == "approve"
        and not request.approved_by.strip()
    ):
        raise HTTPException(
            status_code=422,
            detail="Approver identity is required",
        )

    try:
        result = await resume_incident(
            thread_id=thread_id,
            decision=request.decision,
            approved_by=request.approved_by,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc

    return result
