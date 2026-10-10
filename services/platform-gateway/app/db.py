from __future__ import annotations

import os
from datetime import datetime, timezone

from typing import Any

from sqlalchemy import JSON, DateTime, String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be configured before starting platform-gateway")
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(AsyncAttrs, DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TaskRecord(Base):
    __tablename__ = "platform_tasks"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_platform_tasks_tenant_idempotency"),)

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    agent_ref: Mapped[str] = mapped_column(String(256))
    goal: Mapped[str] = mapped_column(Text)
    input_json: Mapped[dict] = mapped_column(JSON, default=dict)
    constraints_json: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(64), index=True, default="QUEUED")
    trace_id: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProjectRecord(Base):
    __tablename__ = "platform_projects"
    __table_args__ = (UniqueConstraint("tenant_id", "name", name="uq_platform_projects_tenant_name"),)

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="ACTIVE", index=True)
    created_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DatasetRecord(Base):
    __tablename__ = "platform_datasets"
    __table_args__ = (UniqueConstraint("tenant_id", "project_id", "name", name="uq_platform_datasets_scope_name"),)

    dataset_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    project_id: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="DRAFT", index=True)
    latest_version_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DatasetVersionRecord(Base):
    __tablename__ = "platform_dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_label", name="uq_platform_dataset_versions_label"),)

    version_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    version_label: Mapped[str] = mapped_column(String(80))
    schema_fingerprint: Mapped[str] = mapped_column(String(128))
    content_fingerprint: Mapped[str] = mapped_column(String(128))
    row_count: Mapped[int] = mapped_column(default=0)
    columns_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    artifact_uri: Mapped[str] = mapped_column(String(1024))
    quality_status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    created_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEventRecord(Base):
    __tablename__ = "platform_audit_events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    principal: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(160), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(128), index=True)
    trace_id: Mapped[str] = mapped_column(String(128), index=True)
    reason: Mapped[str] = mapped_column(String(512), default="")
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OutboxEventRecord(Base):
    __tablename__ = "platform_outbox_events"

    outbox_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    aggregate_type: Mapped[str] = mapped_column(String(80), index=True)
    aggregate_id: Mapped[str] = mapped_column(String(128), index=True)
    event_type: Mapped[str] = mapped_column(String(160), index=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    attempts: Mapped[int] = mapped_column(default=0)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


async def init_db() -> None:
    if os.getenv("AUTO_CREATE_SCHEMA", "true").lower() != "true":
        return
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

