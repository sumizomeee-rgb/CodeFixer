from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import Any

from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.config_store import canonical_json

UNBOUND_PROJECT_ID = "__unbound__"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _task_id(provider: str, external_id: str) -> str:
    digest = hashlib.sha256(f"{provider}:{external_id}".encode()).hexdigest()[:16]
    return f"task-{digest}"


class TaskStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def ingest(self, ticket: IngestedTicket, project_id: str | None, execution_mode: str, failure: dict[str, object] | None = None) -> dict[str, Any]:
        content_hash = hashlib.sha256(canonical_json(ticket.payload).encode()).hexdigest()
        with self.connection:
            row = self.connection.execute("SELECT id,current_snapshot_id FROM ticket_records WHERE provider_instance_id=? AND external_ticket_id=?", (ticket.provider_instance_id, ticket.external_ticket_id)).fetchone()
            if row is None:
                cursor = self.connection.execute("""INSERT INTO ticket_records(provider_instance_id,external_ticket_id,title,eligible,external_version) VALUES (?,?,?,?,?)""", (ticket.provider_instance_id, ticket.external_ticket_id, ticket.title, int(ticket.eligible), ticket.external_version))
                if cursor.lastrowid is None:
                    raise RuntimeError("ticket record insert returned no row id")
                record_id = cursor.lastrowid
            else:
                record_id = int(row["id"])
                self.connection.execute("""UPDATE ticket_records SET title=?,eligible=?,external_version=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (ticket.title, int(ticket.eligible), ticket.external_version, record_id))
            snap = self.connection.execute("SELECT id FROM ticket_snapshots WHERE ticket_record_id=? AND content_hash=?", (record_id, content_hash)).fetchone()
            is_new_snapshot = snap is None
            if snap is None:
                cursor = self.connection.execute("""INSERT INTO ticket_snapshots(ticket_record_id,content_hash,title,payload_json,external_version) VALUES (?,?,?,?,?)""", (record_id, content_hash, ticket.title, canonical_json(ticket.payload), ticket.external_version))
                if cursor.lastrowid is None:
                    raise RuntimeError("ticket snapshot insert returned no row id")
                snapshot_id = cursor.lastrowid
            else:
                snapshot_id = int(snap["id"])
            self.connection.execute("UPDATE ticket_records SET current_snapshot_id=? WHERE id=?", (snapshot_id, record_id))
            task = self.connection.execute("SELECT * FROM tasks WHERE ticket_record_id=?", (record_id,)).fetchone()
            binding = project_id or UNBOUND_PROJECT_ID
            if task is None:
                task_id = _task_id(ticket.provider_instance_id, ticket.external_ticket_id)
                if failure is not None:
                    status = "failed"
                elif not ticket.eligible:
                    status = "canceled"
                else:
                    status = "queued" if execution_mode == "automatic" else "awaiting_start"
                self.connection.execute("""INSERT INTO tasks(id,ticket_record_id,project_id,status,failure_json) VALUES (?,?,?,?,?)""", (task_id, record_id, binding, status, canonical_json(failure) if failure is not None else None))
                self._event(task_id, "ticket_ingested", {"snapshotId": snapshot_id, "status": status})
                if status == "queued":
                    self._create_run(task_id, execution_mode)
            else:
                task_id = str(task["id"])
                self._event(task_id, "ticket_updated", {"snapshotId": snapshot_id})
                route_recovered = str(task["project_id"]) == UNBOUND_PROJECT_ID and project_id is not None
                if (is_new_snapshot or route_recovered) and task["status"] not in {"queued", "running", "cancel_requested"}:
                    if failure is not None:
                        self.connection.execute("""UPDATE tasks SET project_id=?,status='failed',failure_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (binding, canonical_json(failure), task_id))
                    elif not ticket.eligible:
                        self.connection.execute("""UPDATE tasks SET project_id=?,status='canceled',failure_json=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (binding, task_id))
                    else:
                        next_status = "queued" if execution_mode == "automatic" else "awaiting_start"
                        self.connection.execute("""UPDATE tasks SET project_id=?,status=?,failure_json=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (binding, next_status, task_id))
                        if next_status == "queued":
                            self._create_run(task_id, execution_mode)
            return self.get_task(task_id)

    def _event(self, task_id: str, event_type: str, payload: dict[str, object]) -> None:
        self.connection.execute("INSERT INTO task_events(event_type,payload_json) VALUES (?,?)", (event_type, canonical_json({"taskId": task_id, **payload})))

    def _create_run(self, task_id: str, execution_mode: str) -> str:
        existing = self.connection.execute("SELECT id FROM task_runs WHERE task_id=? AND status IN ('queued','running')", (task_id,)).fetchone()
        if existing is not None:
            return str(existing["id"])
        run_id = f"run-{uuid.uuid4().hex[:18]}"
        self.connection.execute("INSERT INTO task_runs(id,task_id,status,execution_mode_snapshot) VALUES (?,?,?,?)", (run_id, task_id, "queued", execution_mode))
        self.connection.execute("""UPDATE tasks SET current_run_id=?,status=?,failure_json=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (run_id, "queued", task_id))
        self._event(task_id, "run_queued", {"runId": run_id, "mode": execution_mode})
        return run_id

    def start_task(self, task_id: str, execution_mode: str) -> dict[str, Any]:
        task = self.connection.execute("SELECT status,project_id FROM tasks WHERE id=?", (task_id,)).fetchone()
        if task is None:
            raise KeyError(task_id)
        if str(task["project_id"]) == UNBOUND_PROJECT_ID:
            raise ValueError("task has no unique project route")
        if task["status"] not in {"awaiting_start", "failed", "canceled"}:
            raise ValueError(f"task cannot start from {task['status']}")
        with self.connection:
            self._create_run(task_id, execution_mode)
        return self.get_task(task_id)

    def retry_frozen_delivery(self, task_id: str, run_id: str) -> dict[str, Any]:
        row = self.connection.execute("""SELECT t.status AS task_status,t.current_run_id,r.status AS run_status FROM tasks t JOIN task_runs r ON r.task_id=t.id WHERE t.id=? AND r.id=?""", (task_id, run_id)).fetchone()
        if row is None:
            raise KeyError(task_id)
        if str(row["current_run_id"] or "") != run_id:
            raise ValueError("delivery retry is only allowed for the task current run")
        if row["task_status"] != "failed" or row["run_status"] != "failed":
            raise ValueError("delivery retry requires a failed task and failed run")
        with self.connection:
            self.connection.execute("UPDATE task_runs SET status='queued',finished_at=NULL WHERE id=?", (run_id,))
            self.connection.execute("""UPDATE tasks SET status='queued',result=NULL,failure_json=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?""", (task_id,))
            self._event(task_id, "delivery_retry_queued", {"runId": run_id})
        return self.get_task(task_id)

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        row = self.connection.execute("SELECT status,current_run_id FROM tasks WHERE id=?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        with self.connection:
            if row["status"] in {"awaiting_start", "queued"}:
                self.connection.execute("UPDATE tasks SET status='canceled',updated_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
                if row["current_run_id"]:
                    self.connection.execute("UPDATE task_runs SET status='canceled',finished_at=? WHERE id=?", (_now(), row["current_run_id"]))
                self._event(task_id, "task_canceled", {})
            elif row["status"] == "running":
                self.connection.execute("UPDATE tasks SET status='cancel_requested',updated_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
                self._event(task_id, "cancel_requested", {})
            else:
                raise ValueError(f"task cannot cancel from {row['status']}")
        return self.get_task(task_id)

    def is_cancel_requested(self, run_id: str) -> bool:
        row = self.connection.execute("""SELECT t.status FROM task_runs r JOIN tasks t ON t.id=r.task_id WHERE r.id=?""", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return str(row["status"]) == "cancel_requested"

    def cancel_run(self, run_id: str, reason: str = "user_requested") -> None:
        row = self.connection.execute("SELECT task_id,status FROM task_runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        task_id = str(row["task_id"])
        with self.connection:
            self.connection.execute("UPDATE task_runs SET status='canceled',finished_at=COALESCE(finished_at,?) WHERE id=?", (_now(), run_id))
            self.connection.execute("UPDATE tasks SET status='canceled',result=NULL,failure_json=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?", (task_id,))
            self._event(task_id, "run_canceled", {"runId": run_id, "reason": reason})

    def get_cursor(self, provider_instance_id: str) -> str | None:
        row = self.connection.execute("SELECT cursor_value FROM provider_cursors WHERE provider_instance_id=?", (provider_instance_id,)).fetchone()
        return str(row["cursor_value"]) if row is not None and row["cursor_value"] else None

    def set_cursor(self, provider_instance_id: str, cursor: str | None) -> None:
        if cursor is None:
            return
        with self.connection:
            self.connection.execute("""INSERT INTO provider_cursors(provider_instance_id,cursor_value) VALUES (?,?) ON CONFLICT(provider_instance_id) DO UPDATE SET cursor_value=excluded.cursor_value,updated_at=CURRENT_TIMESTAMP""", (provider_instance_id, cursor))

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        sql = "SELECT t.*,tr.provider_instance_id,tr.external_ticket_id,tr.title FROM tasks t JOIN ticket_records tr ON tr.id=t.ticket_record_id"
        params: tuple[object, ...] = ()
        if status:
            sql += " WHERE t.status=?"
            params = (status,)
        sql += " ORDER BY t.updated_at DESC,t.created_at DESC"
        return [self._decode_task(dict(row)) for row in self.connection.execute(sql, params).fetchall()]

    def get_task(self, task_id: str) -> dict[str, Any]:
        row = self.connection.execute("""SELECT t.*,tr.provider_instance_id,tr.external_ticket_id,tr.title,tr.current_snapshot_id FROM tasks t JOIN ticket_records tr ON tr.id=t.ticket_record_id WHERE t.id=?""", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        result = self._decode_task(dict(row))
        runs = [dict(item) for item in self.connection.execute("SELECT * FROM task_runs WHERE task_id=? ORDER BY created_at DESC", (task_id,)).fetchall()]
        for run in runs:
            run_id = str(run["id"])
            run["stages"] = self.list_stages(run_id)
            run["artifacts"] = [dict(item) for item in self.connection.execute("SELECT * FROM artifacts WHERE task_run_id=? ORDER BY id", (run_id,)).fetchall()]
            action_rows = self.connection.execute("SELECT * FROM delivery_action_runs WHERE task_run_id=? ORDER BY id", (run_id,)).fetchall()
            actions: list[dict[str, Any]] = []
            for action_row in action_rows:
                action = dict(action_row)
                raw_result = action.pop("result_json", None)
                action["result"] = json.loads(raw_result) if raw_result else None
                targets = self.connection.execute("SELECT * FROM delivery_target_runs WHERE delivery_action_run_id=? ORDER BY id", (action["id"],)).fetchall()
                action["targets"] = [dict(target) for target in targets]
                actions.append(action)
            run["delivery_actions"] = actions
        result["runs"] = runs
        events = self.connection.execute("""SELECT id,event_type,payload_json,created_at FROM task_events WHERE json_extract(payload_json,'$.taskId')=? ORDER BY id""", (task_id,)).fetchall()
        result["events"] = [{**dict(item), "payload": json.loads(item["payload_json"])} for item in events]
        return result

    @staticmethod
    def _decode_task(result: dict[str, Any]) -> dict[str, Any]:
        raw_failure = result.pop("failure_json", None)
        result["failure"] = json.loads(raw_failure) if raw_failure else None
        if result.get("project_id") == UNBOUND_PROJECT_ID:
            result["project_id"] = None
        return result

    def claim_run(self, run_id: str, worker_id: str = "local-worker") -> dict[str, Any]:
        with self.connection:
            row = self.connection.execute("""SELECT r.*,t.ticket_record_id,t.project_id,t.id AS task_id,tr.current_snapshot_id FROM task_runs r JOIN tasks t ON t.id=r.task_id JOIN ticket_records tr ON tr.id=t.ticket_record_id WHERE r.id=?""", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            if row["status"] != "queued":
                raise ValueError(f"run cannot be claimed from {row['status']}")
            snapshot_id = row["ticket_snapshot_id"] or row["current_snapshot_id"]
            if snapshot_id is None:
                raise ValueError("task has no current ticket snapshot")
            now = _now()
            self.connection.execute("""UPDATE task_runs SET status='running',ticket_snapshot_id=?,started_at=COALESCE(started_at,?) WHERE id=? AND status='queued'""", (snapshot_id, now, run_id))
            self.connection.execute("UPDATE tasks SET status='running',updated_at=CURRENT_TIMESTAMP WHERE id=?", (row["task_id"],))
            self._event(str(row["task_id"]), "run_started", {"runId": run_id, "workerId": worker_id})
        return self.get_run_context(run_id)

    def freeze_run_inputs(self, run_id: str, *, project_config_hash: str, input_fingerprint: str) -> None:
        with self.connection:
            self.connection.execute("UPDATE task_runs SET project_config_hash=?,input_fingerprint=? WHERE id=?", (project_config_hash, input_fingerprint, run_id))

    def get_run_context(self, run_id: str) -> dict[str, Any]:
        row = self.connection.execute("""SELECT r.*,t.id AS task_id,t.project_id,t.ticket_record_id,tr.provider_instance_id,tr.external_ticket_id,tr.title,s.payload_json,s.content_hash AS ticket_content_hash,s.external_version FROM task_runs r JOIN tasks t ON t.id=r.task_id JOIN ticket_records tr ON tr.id=t.ticket_record_id JOIN ticket_snapshots s ON s.id=r.ticket_snapshot_id WHERE r.id=?""", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        result = dict(row)
        result["ticket_payload"] = json.loads(result.pop("payload_json"))
        return result

    def start_stage(self, run_id: str, stage_id: str, attempt: int = 1) -> int:
        with self.connection:
            cursor = self.connection.execute("""INSERT INTO stage_runs(task_run_id,stage_id,attempt,status,started_at) VALUES (?,?,?,'running',?)""", (run_id, stage_id, attempt, _now()))
            if cursor.lastrowid is None:
                raise RuntimeError("stage insert returned no id")
            return int(cursor.lastrowid)

    def finish_stage(self, stage_run_id: int, *, status: str, output_path: str | None = None, failure: dict[str, object] | None = None) -> None:
        with self.connection:
            self.connection.execute("UPDATE stage_runs SET status=?,output_path=?,failure_json=?,finished_at=? WHERE id=?", (status, output_path, canonical_json(failure) if failure is not None else None, _now(), stage_run_id))

    def complete_run(self, run_id: str, result: str) -> None:
        with self.connection:
            row = self.connection.execute("SELECT task_id FROM task_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            self.connection.execute("UPDATE task_runs SET status='completed',finished_at=? WHERE id=?", (_now(), run_id))
            self.connection.execute("UPDATE tasks SET status='completed',result=?,failure_json=NULL,updated_at=CURRENT_TIMESTAMP WHERE id=?", (result, row["task_id"]))
            self._event(str(row["task_id"]), "run_completed", {"runId": run_id, "result": result})

    def fail_run(self, run_id: str, failure: dict[str, object]) -> None:
        with self.connection:
            row = self.connection.execute("SELECT task_id FROM task_runs WHERE id=?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            encoded = canonical_json(failure)
            self.connection.execute("UPDATE task_runs SET status='failed',finished_at=? WHERE id=?", (_now(), run_id))
            self.connection.execute("UPDATE tasks SET status='failed',result=NULL,failure_json=?,updated_at=CURRENT_TIMESTAMP WHERE id=?", (encoded, row["task_id"]))
            self._event(str(row["task_id"]), "run_failed", {"runId": run_id, "failure": failure})

    def list_queued_run_ids(self, limit: int = 100) -> list[str]:
        rows = self.connection.execute("SELECT id FROM task_runs WHERE status='queued' ORDER BY created_at,id LIMIT ?", (limit,)).fetchall()
        return [str(row["id"]) for row in rows]

    def get_run_summary(self, run_id: str) -> dict[str, Any]:
        row = self.connection.execute("""SELECT r.id,r.task_id,r.status,r.execution_mode_snapshot,t.project_id,t.status AS task_status,tr.provider_instance_id,tr.external_ticket_id FROM task_runs r JOIN tasks t ON t.id=r.task_id JOIN ticket_records tr ON tr.id=t.ticket_record_id WHERE r.id=?""", (run_id,)).fetchone()
        if row is None:
            raise KeyError(run_id)
        return dict(row)

    def list_stages(self, run_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute("SELECT * FROM stage_runs WHERE task_run_id=? ORDER BY id", (run_id,)).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            raw = item.pop("failure_json", None)
            item["failure"] = json.loads(raw) if raw else None
            result.append(item)
        return result

    def next_stage_attempt(self, run_id: str, stage_id: str) -> int:
        row = self.connection.execute("SELECT COALESCE(MAX(attempt),0) AS value FROM stage_runs WHERE task_run_id=? AND stage_id=?", (run_id, stage_id)).fetchone()
        return int(row["value"]) + 1
