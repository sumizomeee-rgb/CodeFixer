from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any

from codefixer.infrastructure.config_store import canonical_json


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DeliveryStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def ensure_action(
        self,
        *,
        task_run_id: str,
        action_id: str,
        action_version: int,
        action_type: str,
        config_hash: str,
        intent_key: str,
    ) -> dict[str, Any]:
        with self.connection:
            row = self.connection.execute(
                "SELECT * FROM delivery_action_runs WHERE intent_key=?", (intent_key,)
            ).fetchone()
            if row is None:
                cursor = self.connection.execute(
                    """INSERT INTO delivery_action_runs(
                           task_run_id,action_id,action_version,action_type,config_hash,status,intent_key
                       ) VALUES (?,?,?,?,?,'pending',?)""",
                    (task_run_id, action_id, action_version, action_type, config_hash, intent_key),
                )
                if cursor.lastrowid is None:
                    raise RuntimeError("delivery action insert returned no id")
                row = self.connection.execute(
                    "SELECT * FROM delivery_action_runs WHERE id=?", (cursor.lastrowid,)
                ).fetchone()
        return self._decode(row)

    def mark_action(
        self,
        action_run_id: int,
        *,
        status: str,
        outcome: str | None = None,
        result: dict[str, object] | None = None,
    ) -> None:
        with self.connection:
            started = _now() if status in {"running", "reconciling"} else None
            finished = _now() if status in {"succeeded", "failed", "skipped"} else None
            self.connection.execute(
                """UPDATE delivery_action_runs SET status=?,outcome=?,result_json=?,
                   started_at=COALESCE(started_at,?),finished_at=COALESCE(?,finished_at) WHERE id=?""",
                (
                    status,
                    outcome,
                    canonical_json(result) if result is not None else None,
                    started,
                    finished,
                    action_run_id,
                ),
            )

    def ensure_target(self, action_run_id: int, target_key: str) -> dict[str, Any]:
        with self.connection:
            self.connection.execute(
                """INSERT INTO delivery_target_runs(delivery_action_run_id,target_key,status)
                   VALUES (?,?,'pending') ON CONFLICT(delivery_action_run_id,target_key) DO NOTHING""",
                (action_run_id, target_key),
            )
            row = self.connection.execute(
                "SELECT * FROM delivery_target_runs WHERE delivery_action_run_id=? AND target_key=?",
                (action_run_id, target_key),
            ).fetchone()
        return self._decode(row)

    def mark_target(
        self,
        target_run_id: int,
        *,
        status: str,
        outcome: str | None = None,
        remote_ref: str | None = None,
        external_id: str | None = None,
        external_url: str | None = None,
        result: dict[str, object] | None = None,
    ) -> None:
        with self.connection:
            started = _now() if status in {"running", "reconciling"} else None
            finished = _now() if status in {"succeeded", "failed", "skipped"} else None
            self.connection.execute(
                """UPDATE delivery_target_runs SET status=?,outcome=?,remote_ref=COALESCE(?,remote_ref),
                   external_id=COALESCE(?,external_id),external_url=COALESCE(?,external_url),result_json=?,
                   started_at=COALESCE(started_at,?),finished_at=COALESCE(?,finished_at) WHERE id=?""",
                (
                    status,
                    outcome,
                    remote_ref,
                    external_id,
                    external_url,
                    canonical_json(result) if result is not None else None,
                    started,
                    finished,
                    target_run_id,
                ),
            )

    def get_action(self, action_run_id: int) -> dict[str, Any]:
        row = self.connection.execute(
            "SELECT * FROM delivery_action_runs WHERE id=?", (action_run_id,)
        ).fetchone()
        if row is None:
            raise KeyError(action_run_id)
        result = self._decode(row)
        targets = self.connection.execute(
            "SELECT * FROM delivery_target_runs WHERE delivery_action_run_id=? ORDER BY id",
            (action_run_id,),
        ).fetchall()
        result["targets"] = [self._decode(item) for item in targets]
        return result

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise KeyError("delivery row not found")
        value = dict(row)
        raw = value.pop("result_json", None)
        value["result"] = json.loads(raw) if raw else None
        return value
