CREATE TABLE IF NOT EXISTS project_health (
    project_id TEXT PRIMARY KEY,
    ready INTEGER NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    checks_json TEXT NOT NULL,
    checked_at TEXT NOT NULL
);
