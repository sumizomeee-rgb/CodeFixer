from __future__ import annotations

import sqlite3
from pathlib import Path

from codefixer.infrastructure.config_store import canonical_json


class RecoveryService:
    def __init__(self, connection: sqlite3.Connection, data_root: Path):
        self.connection = connection
        self.data_root = data_root.resolve()

    def recover_interrupted_runs(self) -> dict[str, int]:
        rows = self.connection.execute(
            """SELECT r.id AS run_id,r.task_id,t.status AS task_status
               FROM task_runs r JOIN tasks t ON t.id=r.task_id
               WHERE r.status='running'"""
        ).fetchall()
        delivery_resume = 0
        failed_before_freeze = 0
        with self.connection:
            for row in rows:
                run_id = str(row["run_id"])
                task_id = str(row["task_id"])
                manifest = self.data_root / "tasks" / task_id / "runs" / run_id / "freeze-change" / "change-manifest.json"
                running_stages = self.connection.execute(
                    "SELECT id FROM stage_runs WHERE task_run_id=? AND status='running'", (run_id,)
                ).fetchall()
                interruption = canonical_json(
                    {"code": "service_interrupted", "stage": "recovery", "summary": "Service stopped while this stage was running"}
                )
                for stage in running_stages:
                    self.connection.execute(
                        "UPDATE stage_runs SET status='failed',failure_json=?,finished_at=CURRENT_TIMESTAMP WHERE id=?",
                        (interruption, stage["id"]),
                    )
                if manifest.is_file():
                    self.connection.execute("UPDATE task_runs SET status='queued' WHERE id=?", (run_id,))
                    self.connection.execute("UPDATE tasks SET status='queued',failure_json=NULL WHERE id=?", (task_id,))
                    self._event(task_id, "delivery_recovery_queued", {"runId": run_id})
                    delivery_resume += 1
                else:
                    failure = {
                        "code": "service_interrupted_before_freeze",
                        "stage": "recovery",
                        "summary": "Service stopped before an immutable change was frozen; start a new TaskRun to retry safely",
                        "retryable": True,
                        "side_effects": [],
                    }
                    self.connection.execute(
                        "UPDATE task_runs SET status='failed',finished_at=CURRENT_TIMESTAMP WHERE id=?", (run_id,)
                    )
                    self.connection.execute(
                        "UPDATE tasks SET status='failed',result=NULL,failure_json=? WHERE id=?",
                        (canonical_json(failure), task_id),
                    )
                    self._event(task_id, "run_interrupted", {"runId": run_id, "failure": failure})
                    failed_before_freeze += 1
        return {"deliveryResume": delivery_resume, "failedBeforeFreeze": failed_before_freeze}

    def _event(self, task_id: str, event_type: str, payload: dict[str, object]) -> None:
        self.connection.execute(
            "INSERT INTO task_events(event_type,payload_json) VALUES (?,?)",
            (event_type, canonical_json({"taskId": task_id, **payload})),
        )
