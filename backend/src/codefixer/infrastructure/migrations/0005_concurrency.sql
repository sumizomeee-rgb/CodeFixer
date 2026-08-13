CREATE TABLE IF NOT EXISTS llm_slot_waiters (
    queue_position INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    owner TEXT NOT NULL,
    task_run_id TEXT,
    stage_id TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'queued'
        CHECK(state IN ('queued', 'granted', 'released', 'expired', 'canceled')),
    enqueued_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    granted_at TEXT,
    finished_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_llm_slot_waiters_fair_queue
ON llm_slot_waiters(state, queue_position);

CREATE INDEX IF NOT EXISTS idx_llm_slot_waiters_expiry
ON llm_slot_waiters(state, expires_at);

CREATE TABLE IF NOT EXISTS llm_slot_leases (
    slot_number INTEGER PRIMARY KEY,
    request_id TEXT NOT NULL UNIQUE REFERENCES llm_slot_waiters(request_id) ON DELETE CASCADE,
    owner TEXT NOT NULL,
    task_run_id TEXT,
    stage_id TEXT NOT NULL,
    acquired_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    row_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_llm_slot_leases_expiry
ON llm_slot_leases(expires_at);

CREATE TABLE IF NOT EXISTS baseline_cohorts (
    id TEXT PRIMARY KEY,
    cohort_key TEXT NOT NULL,
    source_type TEXT NOT NULL CHECK(source_type IN ('git', 'svn')),
    leader_task_run_id TEXT NOT NULL REFERENCES task_runs(id) ON DELETE CASCADE,
    state TEXT NOT NULL DEFAULT 'open'
        CHECK(state IN ('open', 'resolving', 'sealed', 'failed')),
    created_at TEXT NOT NULL,
    join_deadline TEXT NOT NULL,
    baseline_revision TEXT,
    resolved_at TEXT,
    failure_json TEXT,
    updated_at TEXT NOT NULL,
    row_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_baseline_cohorts_joinable
ON baseline_cohorts(cohort_key, state, join_deadline, created_at DESC);

CREATE TABLE IF NOT EXISTS baseline_cohort_members (
    cohort_id TEXT NOT NULL REFERENCES baseline_cohorts(id) ON DELETE CASCADE,
    task_run_id TEXT NOT NULL UNIQUE REFERENCES task_runs(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('leader', 'follower')),
    joined_at TEXT NOT NULL,
    PRIMARY KEY(cohort_id, task_run_id)
);

CREATE INDEX IF NOT EXISTS idx_baseline_cohort_members_cohort
ON baseline_cohort_members(cohort_id, joined_at);
