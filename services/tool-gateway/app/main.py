from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool: str = Field(min_length=1)
    args: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "L0"
    idempotency_key: str = Field(min_length=1)


ALLOWED_READ_TOOLS = {"dataset.profile", "dataset.sample", "chart.heatmap", "knowledge.search"}
app = FastAPI(title="Industrial AI Tool Gateway", version=os.getenv("BUILD_VERSION", "0.1.0-dev"))


@app.get("/health")
async def health():
    return {"status": "ok", "service": "tool-gateway"}


@app.post("/internal/v1/tools:call")
async def call_tool(payload: ToolCall):
    if payload.tool not in ALLOWED_READ_TOOLS:
        raise HTTPException(status_code=403, detail="Tool is not registered for local execution")
    return {
        "tool": payload.tool,
        "status": "SUCCEEDED",
        "artifact_refs": [],
        "evidence_refs": [],
        "result": {"message": "Tool adapter is ready for a governed connector"},
    }


