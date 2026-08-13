from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

BaselineCohortState = Literal["open", "resolving", "sealed", "failed"]
BaselineCohortRole = Literal["leader", "follower"]


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(value: datetime) -> str:
    return value.isoformat()


def _parse(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


@contextmanager
def _immediate(connection: sqlite3.Connection) -> Iterator[None]:
    if connection.in_transaction:
        raise RuntimeError("baseline cohort store requires a connection without an active transaction")
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


@dataclass(frozen=True)
class BaselineCohortMembership:
    cohort_id: str
    cohort_key: str
    source_type: str
    task_run_id: str
    leader_task_run_id: str
    role: BaselineCohortRole
    state: BaselineCohortState
    created_at: datetime
    join_deadline: datetime
    baseline_revision: str | None
    resolved_at: datetime | None
    failure: dict[str, object] | None
    row_version: int

    @property
    def is_leader(self) -> bool:
        return self.role == "leader"


class BaselineCohortStore:
    """Durable membership and immutable baseline fact for short-lived source cohorts."""

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def join_or_create(
        self,
        *,
        cohort_key: str,
        source_type: str,
        task_run_id: str,
        window_ms: int = 2000,
        now: datetime | None = None,
    ) -> BaselineCohortMembership:
        if source_type not in {"git", "svn"}:
            raise ValueError(f"unsupported cohort source type: {source_type}")
        if window_ms < 0:
            raise ValueError("baseline cohort window cannot be negative")
        current = now or _now()
        with _immediate(self.connection):
            self._advance_expired_locked(current)
            existing = self._select_membership(task_run_id)
            if existing is not None:
                if str(existing["cohort_key"]) != cohort_key:
                    raise ValueError(
                        f"task run already belongs to another baseline cohort: {task_run_id}"
                    )
                return self._membership(existing)

            cohort = self.connection.execute(
                """SELECT * FROM baseline_cohorts
                   WHERE cohort_key=? AND source_type=? AND state='open' AND join_deadline>?
                   ORDER BY created_at DESC LIMIT 1""",
                (cohort_key, source_type, _stamp(current)),
            ).fetchone()
            if cohort is None:
                cohort_id = str(uuid.uuid4())
                deadline = current + timedelta(milliseconds=window_ms)
                self.connection.execute(
                    """INSERT INTO baseline_cohorts(
                           id,cohort_key,source_type,leader_task_run_id,state,created_at,
                           join_deadline,updated_at
                       ) VALUES (?,?,?,?, 'open', ?,?,?)""",
                    (
                        cohort_id,
                        cohort_key,
                        source_type,
                        task_run_id,
                        _stamp(current),
                        _stamp(deadline),
                        _stamp(current),
                    ),
                )
                role = "leader"
            else:
                cohort_id = str(cohort["id"])
                role = "follower"
            self.connection.execute(
                """INSERT INTO baseline_cohort_members(
                       cohort_id,task_run_id,role,joined_at
                   ) VALUES (?,?,?,?)""",
                (cohort_id, task_run_id, role, _stamp(current)),
            )
            row = self._select_membership(task_run_id)
            assert row is not None
            return self._membership(row)

    def get_for_task(
        self, task_run_id: str, *, now: datetime | None = None
    ) -> BaselineCohortMembership:
        current = now or _now()
        with _immediate(self.connection):
            self._advance_expired_locked(current)
            row = self._select_membership(task_run_id)
            if row is None:
                raise KeyError(f"baseline cohort membership not found: {task_run_id}")
            return self._membership(row)

    def resolve(
        self,
        *,
        cohort_id: str,
        leader_task_run_id: str,
        baseline_revision: str,
        now: datetime | None = None,
    ) -> BaselineCohortMembership:
        revision = baseline_revision.strip()
        if not revision:
            raise ValueError("baseline revision cannot be empty")
        current = now or _now()
        with _immediate(self.connection):
            row = self.connection.execute(
                "SELECT * FROM baseline_cohorts WHERE id=?", (cohort_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"baseline cohort not found: {cohort_id}")
            if str(row["leader_task_run_id"]) != leader_task_run_id:
                raise PermissionError(f"only the baseline cohort leader may resolve: {cohort_id}")
            previous = row["baseline_revision"]
            if previous is not None and str(previous) != revision:
                raise ValueError(f"baseline cohort revision is immutable: {cohort_id}")
            if str(row["state"]) == "failed":
                raise ValueError(f"failed baseline cohort cannot be resolved: {cohort_id}")
            state = "sealed" if _parse(row["join_deadline"]) <= current else "open"
            self.connection.execute(
                """UPDATE baseline_cohorts
                   SET baseline_revision=?,resolved_at=COALESCE(resolved_at,?),state=?,
                       updated_at=?,row_version=row_version+1
                   WHERE id=?""",
                (revision, _stamp(current), state, _stamp(current), cohort_id),
            )
            member = self._select_membership(leader_task_run_id)
            assert member is not None
            return self._membership(member)

    def fail(
        self,
        *,
        cohort_id: str,
        leader_task_run_id: str,
        failure: dict[str, object],
        now: datetime | None = None,
    ) -> BaselineCohortMembership:
        current = now or _now()
        failure_json = json.dumps(failure, ensure_ascii=False, sort_keys=True)
        with _immediate(self.connection):
            row = self.connection.execute(
                "SELECT * FROM baseline_cohorts WHERE id=?", (cohort_id,)
            ).fetchone()
            if row is None:
                raise KeyError(f"baseline cohort not found: {cohort_id}")
            if str(row["leader_task_run_id"]) != leader_task_run_id:
                raise PermissionError(f"only the baseline cohort leader may fail: {cohort_id}")
            if row["baseline_revision"] is not None:
                raise ValueError(f"resolved baseline cohort cannot be failed: {cohort_id}")
            if str(row["state"]) != "failed":
                self.connection.execute(
                    """UPDATE baseline_cohorts
                       SET state='failed',failure_json=?,updated_at=?,row_version=row_version+1
                       WHERE id=?""",
                    (failure_json, _stamp(current), cohort_id),
                )
            member = self._select_membership(leader_task_run_id)
            assert member is not None
            return self._membership(member)

    def member_count(self, cohort_id: str) -> int:
        return int(
            self.connection.execute(
                "SELECT COUNT(*) FROM baseline_cohort_members WHERE cohort_id=?", (cohort_id,)
            ).fetchone()[0]
        )

    def _advance_expired_locked(self, now: datetime) -> None:
        stamp = _stamp(now)
        self.connection.execute(
            """UPDATE baseline_cohorts
               SET state='sealed',updated_at=?,row_version=row_version+1
               WHERE state='open' AND join_deadline<=? AND baseline_revision IS NOT NULL""",
            (stamp, stamp),
        )
        self.connection.execute(
            """UPDATE baseline_cohorts
               SET state='resolving',updated_at=?,row_version=row_version+1
               WHERE state='open' AND join_deadline<=? AND baseline_revision IS NULL""",
            (stamp, stamp),
        )

    def _select_membership(self, task_run_id: str) -> sqlite3.Row | None:
        row = self.connection.execute(
            """SELECT c.*,m.task_run_id,m.role
               FROM baseline_cohort_members m
               JOIN baseline_cohorts c ON c.id=m.cohort_id
               WHERE m.task_run_id=?""",
            (task_run_id,),
        ).fetchone()
        return cast(sqlite3.Row | None, row)

    @staticmethod
    def _membership(row: sqlite3.Row) -> BaselineCohortMembership:
        failure_raw = row["failure_json"]
        failure = json.loads(str(failure_raw)) if failure_raw is not None else None
        return BaselineCohortMembership(
            cohort_id=str(row["id"]),
            cohort_key=str(row["cohort_key"]),
            source_type=str(row["source_type"]),
            task_run_id=str(row["task_run_id"]),
            leader_task_run_id=str(row["leader_task_run_id"]),
            role=cast(BaselineCohortRole, str(row["role"])),
            state=cast(BaselineCohortState, str(row["state"])),
            created_at=_parse(row["created_at"]),
            join_deadline=_parse(row["join_deadline"]),
            baseline_revision=(
                str(row["baseline_revision"])
                if row["baseline_revision"] is not None
                else None
            ),
            resolved_at=(
                _parse(row["resolved_at"]) if row["resolved_at"] is not None else None
            ),
            failure=failure,
            row_version=int(row["row_version"]),
        )
