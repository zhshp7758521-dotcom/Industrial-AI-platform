"""Production-oriented control-plane gateway.

The local adapter uses an embedded event publisher; production replaces it with
Kafka/Redpanda without changing the API contract.
"""
from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select

from .db import SessionLocal, TaskRecord, init_db


SERVICE_NAME = "platform-gateway"
BUILD_VERSION = os.getenv("BUILD_VERSION", "0.1.0-dev")


class TaskCreate(BaseModel):
    tenant_id: str = Field(min_length=1)
    project_id: str | None = None
    agent_ref: str = Field(min_length=1)
    goal: str = Field(min_length=1, max_length=4000)
    input: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)


class TaskView(BaseModel):
    task_id: str
    status: str
    trace_id: str
    artifact_refs: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    result: dict[str, Any] | None = None


def view_from_record(record: TaskRecord) -> TaskView:
    return TaskView(
        task_id=record.task_id,
        status=record.status,
        trace_id=record.trace_id,
        result=record.result_json,
    )


async def execute_local(task_id: str) -> None:
    """Deterministic local adapter; production delegates to Temporal workers."""
    await asyncio.sleep(0.05)
    async with SessionLocal() as session:
        record = await session.get(TaskRecord, task_id)
        if record is None:
            return
        record.status = "RUNNING"
        await session.commit()
        await asyncio.sleep(0.05)
        record.status = "SUCCEEDED"
        record.result_json = {
            "message": "Task persisted through PostgreSQL control-plane storage",
            "task_id": task_id,
            "next_step": "Dispatch the task to Temporal workers in production",
        }
        await session.commit()


app = FastAPI(title="Industrial AI Platform Gateway", version=BUILD_VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    trace_id = request.headers.get("x-trace-id", str(uuid.uuid4()))
    response = await call_next(request)
    response.headers["x-trace-id"] = trace_id
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE_NAME, "version": BUILD_VERSION}


@app.get("/ready")
async def ready() -> dict[str, str]:
    return {"status": "ready", "service": SERVICE_NAME}


@app.post("/v1/tasks", response_model=TaskView, status_code=202)
async def create_task(
    payload: TaskCreate,
    background: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
) -> TaskView:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    task_id = f"task-{uuid.uuid4().hex}"
    async with SessionLocal() as session:
        existing = await session.scalar(select(TaskRecord).where(TaskRecord.idempotency_key == idempotency_key))
        if existing is not None:
            return view_from_record(existing)
        record = TaskRecord(
            task_id=task_id,
            tenant_id=payload.tenant_id,
            project_id=payload.project_id,
            agent_ref=payload.agent_ref,
            goal=payload.goal,
            input_json=payload.input,
            constraints_json=payload.constraints,
            status="QUEUED",
            trace_id=trace_id or str(uuid.uuid4()),
            idempotency_key=idempotency_key,
        )
        session.add(record)
        await session.commit()
        task = view_from_record(record)
    background.add_task(execute_local, task_id)
    return task


@app.get("/v1/tasks/{task_id}", response_model=TaskView)
async def get_task(task_id: str) -> TaskView:
    async with SessionLocal() as session:
        record = await session.get(TaskRecord, task_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return view_from_record(record)


