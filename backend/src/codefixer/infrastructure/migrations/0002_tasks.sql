CREATE TABLE IF NOT EXISTS ticket_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider_instance_id TEXT NOT NULL,
    external_ticket_id TEXT NOT NULL,
    title TEXT NOT NULL,
    eligible INTEGER NOT NULL DEFAULT 1,
    external_version TEXT,
    current_snapshot_id INTEGER,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider_instance_id, external_ticket_id)
);

CREATE TABLE IF NOT EXISTS ticket_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_record_id INTEGER NOT NULL REFERENCES ticket_records(id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    title TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    external_version TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticket_record_id, content_hash)
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    ticket_record_id INTEGER NOT NULL REFERENCES ticket_records(id),
    project_id TEXT NOT NULL,
    status TEXT NOT NULL,
    result TEXT,
    current_run_id TEXT,
    ignored_at TEXT,
    archived_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticket_record_id, project_id)
);

CREATE TABLE IF NOT EXISTS task_runs (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    execution_mode_snapshot TEXT NOT NULL,
    ticket_snapshot_id INTEGER,
    project_config_hash TEXT,
    input_fingerprint TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    finished_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_run_per_task
ON task_runs(task_id)
WHERE status IN ('queued', 'running');

CREATE TABLE IF NOT EXISTS stage_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_run_id TEXT NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
    stage_id TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL,
    input_fingerprint TEXT,
    lease_owner TEXT,
    lease_expires_at TEXT,
    started_at TEXT,
    finished_at TEXT,
    output_path TEXT,
    failure_json TEXT,
    UNIQUE(task_run_id, stage_id, attempt)
);

CREATE TABLE IF NOT EXISTS worker_leases (
    resource_key TEXT PRIMARY KEY,
    owner TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    row_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS provider_cursors (
    provider_instance_id TEXT PRIMARY KEY,
    cursor_value TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_task_runs_task ON task_runs(task_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ticket_snapshots_record ON ticket_snapshots(ticket_record_id, created_at DESC);
