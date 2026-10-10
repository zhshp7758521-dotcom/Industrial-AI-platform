from __future__ import annotations

import os
from datetime import datetime, timezone

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


class TaskRecord(Base):
    __tablename__ = "platform_tasks"
    __table_args__ = (UniqueConstraint("idempotency_key", name="uq_platform_tasks_idempotency"),)

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
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


async def init_db() -> None:
    if os.getenv("AUTO_CREATE_SCHEMA", "true").lower() != "true":
        return
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

