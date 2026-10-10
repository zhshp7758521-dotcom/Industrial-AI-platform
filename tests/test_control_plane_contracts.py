import json
import os
import sys
from pathlib import Path

import pytest
from starlette.requests import Request


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "platform-gateway"))
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@127.0.0.1:5432/test")

from app import main  # noqa: E402


def make_request(headers: dict[str, str] | None = None) -> Request:
    encoded_headers = [(key.lower().encode(), value.encode()) for key, value in (headers or {}).items()]
    scope = {"type": "http", "headers": encoded_headers, "method": "GET", "path": "/", "query_string": b""}
    return Request(scope)


def test_request_fingerprint_is_stable_and_payload_sensitive() -> None:
    first = main.TaskCreate(tenant_id="tenant-a", agent_ref="agent@1", goal="profile", input={"a": 1})
    same = main.TaskCreate(tenant_id="tenant-a", agent_ref="agent@1", goal="profile", input={"a": 1})
    changed = main.TaskCreate(tenant_id="tenant-a", agent_ref="agent@1", goal="profile", input={"a": 2})

    assert main.request_fingerprint(first) == main.request_fingerprint(same)
    assert main.request_fingerprint(first) != main.request_fingerprint(changed)


def test_request_context_rejects_mismatched_tenant() -> None:
    request = make_request({"X-Tenant-Id": "tenant-a", "X-Principal": "alice"})
    with pytest.raises(main.HTTPException) as exc_info:
        main.request_context(request, "tenant-b")
    assert exc_info.value.status_code == 403


def test_request_context_requires_identity_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "REQUIRE_IDENTITY_CONTEXT", True)
    request = make_request({"X-Tenant-Id": "tenant-a"})
    with pytest.raises(main.HTTPException) as exc_info:
        main.request_context(request)
    assert exc_info.value.status_code == 401


def test_control_plane_schema_is_valid_json() -> None:
    schema = json.loads((ROOT / "schemas" / "control-plane.schema.json").read_text(encoding="utf-8"))
    assert schema["$schema"].endswith("2020-12/schema")
    assert "projectCreate" in schema["$defs"]
    assert "datasetVersionCreate" in schema["$defs"]


def test_dataset_version_quality_has_closed_state_machine() -> None:
    with pytest.raises(ValueError):
        main.DatasetVersionCreate(
            version_label="v1",
            schema_fingerprint="schema",
            content_fingerprint="content",
            artifact_uri="s3://bucket/object",
            quality_status="APPROVED",
        )


def test_task_idempotency_is_scoped_to_tenant() -> None:
    constraints = main.TaskRecord.__table_args__
    names = {constraint.name for constraint in constraints if constraint.name}
    assert "uq_platform_tasks_tenant_idempotency" in names

