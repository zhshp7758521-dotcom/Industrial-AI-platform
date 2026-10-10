-- Control-plane foundation migration.
-- Run inside a transaction with a migration lock in shared environments.

BEGIN;

ALTER TABLE IF EXISTS platform_tasks
    ADD COLUMN IF NOT EXISTS request_fingerprint VARCHAR(64) NOT NULL DEFAULT '';

ALTER TABLE IF EXISTS platform_tasks
    DROP CONSTRAINT IF EXISTS uq_platform_tasks_idempotency;

ALTER TABLE IF EXISTS platform_tasks
    DROP CONSTRAINT IF EXISTS uq_platform_tasks_tenant_idempotency;

ALTER TABLE IF EXISTS platform_tasks
    ADD CONSTRAINT uq_platform_tasks_tenant_idempotency UNIQUE (tenant_id, idempotency_key);

CREATE TABLE IF NOT EXISTS platform_projects (
    project_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(128) NOT NULL,
    name VARCHAR(160) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    created_by VARCHAR(160) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_platform_projects_tenant_name UNIQUE (tenant_id, name)
);

CREATE INDEX IF NOT EXISTS ix_platform_projects_tenant_id ON platform_projects (tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_projects_status ON platform_projects (status);

CREATE TABLE IF NOT EXISTS platform_datasets (
    dataset_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(128) NOT NULL,
    project_id VARCHAR(64) NOT NULL,
    name VARCHAR(160) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    source_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'DRAFT',
    latest_version_id VARCHAR(64),
    created_by VARCHAR(160) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_platform_datasets_scope_name UNIQUE (tenant_id, project_id, name)
);

CREATE INDEX IF NOT EXISTS ix_platform_datasets_tenant_id ON platform_datasets (tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_datasets_project_id ON platform_datasets (project_id);
CREATE INDEX IF NOT EXISTS ix_platform_datasets_status ON platform_datasets (status);

CREATE TABLE IF NOT EXISTS platform_dataset_versions (
    version_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(128) NOT NULL,
    dataset_id VARCHAR(64) NOT NULL,
    version_label VARCHAR(80) NOT NULL,
    schema_fingerprint VARCHAR(128) NOT NULL,
    content_fingerprint VARCHAR(128) NOT NULL,
    row_count BIGINT NOT NULL DEFAULT 0,
    columns_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    artifact_uri VARCHAR(1024) NOT NULL,
    quality_status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    created_by VARCHAR(160) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_platform_dataset_versions_label UNIQUE (dataset_id, version_label)
);

CREATE INDEX IF NOT EXISTS ix_platform_dataset_versions_tenant_id ON platform_dataset_versions (tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_dataset_versions_dataset_id ON platform_dataset_versions (dataset_id);
CREATE INDEX IF NOT EXISTS ix_platform_dataset_versions_quality_status ON platform_dataset_versions (quality_status);

CREATE TABLE IF NOT EXISTS platform_audit_events (
    event_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(128) NOT NULL,
    principal VARCHAR(160) NOT NULL,
    action VARCHAR(160) NOT NULL,
    resource_type VARCHAR(80) NOT NULL,
    resource_id VARCHAR(128) NOT NULL,
    trace_id VARCHAR(128) NOT NULL,
    reason VARCHAR(512) NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_platform_audit_events_tenant_id ON platform_audit_events (tenant_id);
CREATE INDEX IF NOT EXISTS ix_platform_audit_events_action ON platform_audit_events (action);
CREATE INDEX IF NOT EXISTS ix_platform_audit_events_resource_id ON platform_audit_events (resource_id);
CREATE INDEX IF NOT EXISTS ix_platform_audit_events_trace_id ON platform_audit_events (trace_id);

CREATE TABLE IF NOT EXISTS platform_outbox_events (
    outbox_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(128) NOT NULL,
    aggregate_type VARCHAR(80) NOT NULL,
    aggregate_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(160) NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    attempts INTEGER NOT NULL DEFAULT 0,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_platform_outbox_events_pending
    ON platform_outbox_events (created_at, outbox_id)
    WHERE published_at IS NULL;

COMMIT;

