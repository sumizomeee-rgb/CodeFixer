ALTER TABLE tasks ADD COLUMN failure_json TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_one_task_per_ticket ON tasks(ticket_record_id);
