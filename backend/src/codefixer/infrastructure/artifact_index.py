from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from codefixer.protocols import StoredArtifact


class ArtifactIndex:
    def __init__(self, connection: sqlite3.Connection, data_root: Path):
        self.connection = connection
        self.data_root = data_root.resolve()

    def register(
        self,
        *,
        task_run_id: str,
        stage_id: str,
        artifact_type: str,
        artifact: StoredArtifact,
        attempt: int | None = None,
    ) -> dict[str, Any]:
        path = artifact.path.resolve()
        try:
            relative = path.relative_to(self.data_root).as_posix()
        except ValueError as exc:
            raise ValueError("artifact is outside configured data root") from exc
        with self.connection:
            self.connection.execute(
                """INSERT INTO artifacts(
                       task_run_id,stage_id,attempt,artifact_type,relative_path,sha256,size_bytes
                   ) VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(task_run_id,relative_path) DO UPDATE SET
                       stage_id=excluded.stage_id,
                       attempt=excluded.attempt,
                       artifact_type=excluded.artifact_type,
                       sha256=excluded.sha256,
                       size_bytes=excluded.size_bytes""",
                (
                    task_run_id,
                    stage_id,
                    attempt,
                    artifact_type,
                    relative,
                    artifact.sha256,
                    artifact.size_bytes,
                ),
            )
        return self.get(task_run_id, relative)

    def get(self, task_run_id: str, relative_path: str) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM artifacts WHERE task_run_id=? AND relative_path=?",
            (task_run_id, relative_path),
        ).fetchone()
        if row is None:
            raise KeyError(relative_path)
        result = dict(row)
        result["absolute_path"] = str((self.data_root / relative_path).resolve())
        return result

    def list_for_run(self, task_run_id: str) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM artifacts WHERE task_run_id=? ORDER BY id",
            (task_run_id,),
        ).fetchall()
        return [dict(row) for row in rows]
