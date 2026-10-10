"""Production-oriented control-plane gateway.

The local adapter uses an embedded event publisher; production replaces it with
Kafka/Redpanda without changing the API contract.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any, Literal

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from .db import (
    AuditEventRecord,
    DatasetRecord,
    DatasetVersionRecord,
    OutboxEventRecord,
    ProjectRecord,
    SessionLocal,
    TaskRecord,
    init_db,
)


SERVICE_NAME = "platform-gateway"
BUILD_VERSION = os.getenv("BUILD_VERSION", "0.1.0-dev")
REQUIRE_IDENTITY_CONTEXT = os.getenv("REQUIRE_IDENTITY_CONTEXT", "false").lower() == "true"


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


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)


class ProjectView(BaseModel):
    project_id: str
    tenant_id: str
    name: str
    description: str
    status: str
    created_by: str


class DatasetCreate(BaseModel):
    project_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=2000)
    source_type: str = Field(min_length=1, max_length=64)


class DatasetView(BaseModel):
    dataset_id: str
    tenant_id: str
    project_id: str
    name: str
    description: str
    source_type: str
    status: str
    latest_version_id: str | None = None
    created_by: str


class DatasetVersionCreate(BaseModel):
    version_label: str = Field(min_length=1, max_length=80)
    schema_fingerprint: str = Field(min_length=1, max_length=128)
    content_fingerprint: str = Field(min_length=1, max_length=128)
    row_count: int = Field(default=0, ge=0)
    columns: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)
    artifact_uri: str = Field(min_length=1, max_length=1024)
    quality_status: Literal["PENDING", "PASSED", "FAILED"] = "PENDING"


class DatasetVersionView(BaseModel):
    version_id: str
    dataset_id: str
    version_label: str
    schema_fingerprint: str
    content_fingerprint: str
    row_count: int
    columns: list[dict[str, Any]]
    artifact_uri: str
    quality_status: str
    created_by: str


class AuditEventView(BaseModel):
    event_id: str
    tenant_id: str
    principal: str
    action: str
    resource_type: str
    resource_id: str
    trace_id: str
    reason: str
    created_at: str


def request_context(request: Request, body_tenant_id: str | None = None) -> tuple[str, str]:
    """Resolve tenant/principal from the server-side context.

    Local development permits a body tenant for backwards compatibility. Set
    REQUIRE_IDENTITY_CONTEXT=true in shared environments to reject that mode.
    """
    header_tenant_id = request.headers.get("x-tenant-id")
    principal = request.headers.get("x-principal")
    if header_tenant_id and body_tenant_id and header_tenant_id != body_tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context mismatch")
    tenant_id = header_tenant_id or body_tenant_id
    if REQUIRE_IDENTITY_CONTEXT and (not tenant_id or not principal):
        raise HTTPException(status_code=401, detail="Authenticated tenant context is required")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="X-Tenant-Id is required")
    return tenant_id, principal or "local-dev"


def request_fingerprint(payload: BaseModel) -> str:
    encoded = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def append_control_events(
    session,
    *,
    tenant_id: str,
    principal: str,
    trace_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
    payload: dict[str, Any],
    reason: str = "",
) -> None:
    """Write audit and outbox records in the same transaction as the resource."""
    session.add(
        AuditEventRecord(
            event_id=f"audit-{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            principal=principal,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            trace_id=trace_id,
            reason=reason,
            payload_json=payload,
        )
    )
    session.add(
        OutboxEventRecord(
            outbox_id=f"outbox-{uuid.uuid4().hex}",
            tenant_id=tenant_id,
            aggregate_type=resource_type,
            aggregate_id=resource_id,
            event_type=action,
            payload_json={"trace_id": trace_id, "resource_id": resource_id, **payload},
        )
    )


def view_from_record(record: TaskRecord) -> TaskView:
    return TaskView(
        task_id=record.task_id,
        status=record.status,
        trace_id=record.trace_id,
        result=record.result_json,
    )


def project_view(record: ProjectRecord) -> ProjectView:
    return ProjectView(
        project_id=record.project_id,
        tenant_id=record.tenant_id,
        name=record.name,
        description=record.description,
        status=record.status,
        created_by=record.created_by,
    )


def dataset_view(record: DatasetRecord) -> DatasetView:
    return DatasetView(
        dataset_id=record.dataset_id,
        tenant_id=record.tenant_id,
        project_id=record.project_id,
        name=record.name,
        description=record.description,
        source_type=record.source_type,
        status=record.status,
        latest_version_id=record.latest_version_id,
        created_by=record.created_by,
    )


def dataset_version_view(record: DatasetVersionRecord) -> DatasetVersionView:
    return DatasetVersionView(
        version_id=record.version_id,
        dataset_id=record.dataset_id,
        version_label=record.version_label,
        schema_fingerprint=record.schema_fingerprint,
        content_fingerprint=record.content_fingerprint,
        row_count=record.row_count,
        columns=record.columns_json,
        artifact_uri=record.artifact_uri,
        quality_status=record.quality_status,
        created_by=record.created_by,
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


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Industrial AI Platform Gateway", version=BUILD_VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/v1/projects", response_model=ProjectView, status_code=201)
async def create_project(
    payload: ProjectCreate,
    request: Request,
    trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
) -> ProjectView:
    tenant_id, principal = request_context(request)
    project_id = f"project-{uuid.uuid4().hex}"
    async with SessionLocal() as session:
        record = ProjectRecord(
            project_id=project_id,
            tenant_id=tenant_id,
            name=payload.name,
            description=payload.description,
            created_by=principal,
        )
        session.add(record)
        append_control_events(
            session,
            tenant_id=tenant_id,
            principal=principal,
            trace_id=trace_id or str(uuid.uuid4()),
            action="project.created",
            resource_type="project",
            resource_id=project_id,
            payload={"name": payload.name},
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Project name already exists in this tenant") from exc
        return project_view(record)


@app.get("/v1/projects", response_model=list[ProjectView])
async def list_projects(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[ProjectView]:
    tenant_id, _ = request_context(request)
    async with SessionLocal() as session:
        records = (
            await session.scalars(
                select(ProjectRecord)
                .where(ProjectRecord.tenant_id == tenant_id)
                .order_by(ProjectRecord.created_at, ProjectRecord.project_id)
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [project_view(record) for record in records]


@app.post("/v1/datasets", response_model=DatasetView, status_code=201)
async def create_dataset(
    payload: DatasetCreate,
    request: Request,
    trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
) -> DatasetView:
    tenant_id, principal = request_context(request)
    dataset_id = f"dataset-{uuid.uuid4().hex}"
    async with SessionLocal() as session:
        project = await session.scalar(
            select(ProjectRecord).where(
                ProjectRecord.project_id == payload.project_id,
                ProjectRecord.tenant_id == tenant_id,
            )
        )
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        record = DatasetRecord(
            dataset_id=dataset_id,
            tenant_id=tenant_id,
            project_id=payload.project_id,
            name=payload.name,
            description=payload.description,
            source_type=payload.source_type,
            created_by=principal,
        )
        session.add(record)
        append_control_events(
            session,
            tenant_id=tenant_id,
            principal=principal,
            trace_id=trace_id or str(uuid.uuid4()),
            action="dataset.created",
            resource_type="dataset",
            resource_id=dataset_id,
            payload={"project_id": payload.project_id, "name": payload.name, "source_type": payload.source_type},
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Dataset name already exists in this project") from exc
        return dataset_view(record)


@app.post("/v1/datasets/{dataset_id}/versions", response_model=DatasetVersionView, status_code=201)
async def create_dataset_version(
    dataset_id: str,
    payload: DatasetVersionCreate,
    request: Request,
    trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
) -> DatasetVersionView:
    tenant_id, principal = request_context(request)
    version_id = f"version-{uuid.uuid4().hex}"
    async with SessionLocal() as session:
        dataset = await session.scalar(
            select(DatasetRecord)
            .where(DatasetRecord.dataset_id == dataset_id, DatasetRecord.tenant_id == tenant_id)
            .with_for_update()
        )
        if dataset is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        record = DatasetVersionRecord(
            version_id=version_id,
            tenant_id=tenant_id,
            dataset_id=dataset_id,
            version_label=payload.version_label,
            schema_fingerprint=payload.schema_fingerprint,
            content_fingerprint=payload.content_fingerprint,
            row_count=payload.row_count,
            columns_json=payload.columns,
            artifact_uri=payload.artifact_uri,
            quality_status=payload.quality_status,
            created_by=principal,
        )
        session.add(record)
        dataset.latest_version_id = version_id
        dataset.status = "READY" if payload.quality_status == "PASSED" else "VALIDATING"
        append_control_events(
            session,
            tenant_id=tenant_id,
            principal=principal,
            trace_id=trace_id or str(uuid.uuid4()),
            action="dataset.version.created",
            resource_type="dataset_version",
            resource_id=version_id,
            payload={"dataset_id": dataset_id, "version_label": payload.version_label},
        )
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise HTTPException(status_code=409, detail="Dataset version label already exists") from exc
        return dataset_version_view(record)


@app.get("/v1/datasets/{dataset_id}", response_model=DatasetView)
async def get_dataset(dataset_id: str, request: Request) -> DatasetView:
    tenant_id, _ = request_context(request)
    async with SessionLocal() as session:
        record = await session.scalar(
            select(DatasetRecord).where(
                DatasetRecord.dataset_id == dataset_id,
                DatasetRecord.tenant_id == tenant_id,
            )
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Dataset not found")
        return dataset_view(record)


@app.get("/v1/audit-events", response_model=list[AuditEventView])
async def list_audit_events(
    request: Request,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[AuditEventView]:
    tenant_id, _ = request_context(request)
    async with SessionLocal() as session:
        records = (
            await session.scalars(
                select(AuditEventRecord)
                .where(AuditEventRecord.tenant_id == tenant_id)
                .order_by(AuditEventRecord.created_at.desc(), AuditEventRecord.event_id.desc())
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [
            AuditEventView(
                event_id=record.event_id,
                tenant_id=record.tenant_id,
                principal=record.principal,
                action=record.action,
                resource_type=record.resource_type,
                resource_id=record.resource_id,
                trace_id=record.trace_id,
                reason=record.reason,
                created_at=record.created_at.isoformat(),
            )
            for record in records
        ]


@app.post("/v1/tasks", response_model=TaskView, status_code=202)
async def create_task(
    payload: TaskCreate,
    request: Request,
    background: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    trace_id: str | None = Header(default=None, alias="X-Trace-Id"),
) -> TaskView:
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    tenant_id, principal = request_context(request, payload.tenant_id)
    fingerprint = request_fingerprint(payload)
    task_id = f"task-{uuid.uuid4().hex}"
    async with SessionLocal() as session:
        existing = await session.scalar(
            select(TaskRecord).where(
                TaskRecord.tenant_id == tenant_id,
                TaskRecord.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            if existing.request_fingerprint and existing.request_fingerprint != fingerprint:
                raise HTTPException(status_code=409, detail="Idempotency key was already used for another request")
            return view_from_record(existing)
        record = TaskRecord(
            task_id=task_id,
            tenant_id=tenant_id,
            project_id=payload.project_id,
            agent_ref=payload.agent_ref,
            goal=payload.goal,
            input_json=payload.input,
            constraints_json=payload.constraints,
            status="QUEUED",
            trace_id=trace_id or str(uuid.uuid4()),
            idempotency_key=idempotency_key,
            request_fingerprint=fingerprint,
        )
        session.add(record)
        append_control_events(
            session,
            tenant_id=tenant_id,
            principal=principal,
            trace_id=record.trace_id,
            action="task.created",
            resource_type="task",
            resource_id=task_id,
            payload={"agent_ref": payload.agent_ref, "goal": payload.goal},
        )
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            existing = await session.scalar(
                select(TaskRecord).where(
                    TaskRecord.tenant_id == tenant_id,
                    TaskRecord.idempotency_key == idempotency_key,
                )
            )
            if existing is None or existing.request_fingerprint != fingerprint:
                raise HTTPException(status_code=409, detail="Concurrent idempotency conflict")
            return view_from_record(existing)
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


