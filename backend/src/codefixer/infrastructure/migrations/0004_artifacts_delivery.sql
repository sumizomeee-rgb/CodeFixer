CREATE TABLE IF NOT EXISTS artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_run_id TEXT NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
    stage_id TEXT NOT NULL,
    attempt INTEGER,
    artifact_type TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_run_id, relative_path)
);

CREATE INDEX IF NOT EXISTS idx_artifacts_run_stage
ON artifacts(task_run_id, stage_id, attempt, created_at);

CREATE TABLE IF NOT EXISTS delivery_action_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_run_id TEXT NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
    action_id TEXT NOT NULL,
    action_version INTEGER NOT NULL DEFAULT 1,
    action_type TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    outcome TEXT,
    intent_key TEXT NOT NULL,
    result_json TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(task_run_id, action_id, action_version),
    UNIQUE(intent_key)
);

CREATE TABLE IF NOT EXISTS delivery_target_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    delivery_action_run_id INTEGER NOT NULL REFERENCES delivery_action_runs(id) ON DELETE CASCADE,
    target_key TEXT NOT NULL,
    status TEXT NOT NULL,
    outcome TEXT,
    remote_ref TEXT,
    external_id TEXT,
    external_url TEXT,
    result_json TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(delivery_action_run_id, target_key)
);
