from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    task_id: str
    agent_ref: str
    goal: str = Field(min_length=1)
    input: dict[str, Any] = Field(default_factory=dict)
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class Plan(BaseModel):
    plan_id: str
    risk: str
    steps: list[dict[str, Any]]


app = FastAPI(title="Industrial AI Agent Runtime", version=os.getenv("BUILD_VERSION", "0.1.0-dev"))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent-runtime"}


@app.post("/internal/v1/plan", response_model=Plan)
async def create_plan(payload: ExecuteRequest) -> Plan:
    if not payload.agent_ref:
        raise HTTPException(status_code=400, detail="agent_ref is required")
    return Plan(
        plan_id=f"plan-{uuid.uuid4().hex}",
        risk="L0",
        steps=[
            {
                "step_id": "inspect",
                "tool": "dataset.profile",
                "args": payload.input,
                "side_effect": "none",
            },
            {
                "step_id": "summarize",
                "tool": "report.create",
                "args": {"goal": payload.goal},
                "side_effect": "none",
            },
        ],
    )


