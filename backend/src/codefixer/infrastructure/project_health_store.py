from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from codefixer.infrastructure.config_store import canonical_json


class ProjectHealthStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def put(self, result: dict[str, Any]) -> dict[str, Any]:
        project_id = str(result.get("projectId") or "").strip()
        if not project_id:
            raise ValueError("project health requires projectId")
        checked_at = datetime.now(UTC).isoformat()
        payload = {
            "projectId": project_id,
            "ready": bool(result.get("ready")),
            "status": str(result.get("status") or "not_ready"),
            "summary": str(result.get("summary") or "流水线状态未知"),
            "checks": list(result.get("checks") or []),
            "checkedAt": checked_at,
        }
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO project_health(project_id,ready,status,summary,checks_json,checked_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(project_id) DO UPDATE SET
                    ready=excluded.ready,
                    status=excluded.status,
                    summary=excluded.summary,
                    checks_json=excluded.checks_json,
                    checked_at=excluded.checked_at
                """,
                (
                    project_id,
                    int(payload["ready"]),
                    payload["status"],
                    payload["summary"],
                    canonical_json(payload["checks"]),
                    checked_at,
                ),
            )
        return payload

    def get(self, project_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM project_health WHERE project_id=?",
            (project_id,),
        ).fetchone()
        if row is None:
            return None
        return {
            "projectId": str(row["project_id"]),
            "ready": bool(row["ready"]),
            "status": str(row["status"]),
            "summary": str(row["summary"]),
            "checks": json.loads(str(row["checks_json"])),
            "checkedAt": str(row["checked_at"]),
        }

    def list(self) -> dict[str, dict[str, Any]]:
        rows = self.connection.execute("SELECT project_id FROM project_health").fetchall()
        return {
            str(row["project_id"]): value
            for row in rows
            if (value := self.get(str(row["project_id"]))) is not None
        }
