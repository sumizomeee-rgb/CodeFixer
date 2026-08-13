from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


class LlmSlotLeaseLostError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(value: datetime) -> str:
    return value.isoformat()


def _parse(value: object) -> datetime:
    return datetime.fromisoformat(str(value))


@dataclass(frozen=True)
class LlmSlotLease:
    slot_number: int
    request_id: str
    owner: str
    task_run_id: str | None
    stage_id: str
    acquired_at: datetime
    expires_at: datetime
    queue_position: int
    enqueued_at: datetime


@dataclass(frozen=True)
class LlmSlotSnapshot:
    capacity: int
    active: int
    waiting: int
    expired_reclaimed: int = 0


@contextmanager
def _immediate(connection: sqlite3.Connection) -> Iterator[None]:
    if connection.in_transaction:
        raise RuntimeError("LLM slot store requires a connection without an active transaction")
    connection.execute("BEGIN IMMEDIATE")
    try:
        yield
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


class LlmSlotStore:
    """Persistent, FIFO global Agent-process lease store.

    A waiter first obtains a durable queue position, then only the oldest waiter may
    claim the next free slot. ``BEGIN IMMEDIATE`` serializes the short allocation
    decision across scheduler/executor connections without holding a database lock
    while an Agent process is running.
    """

    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def enqueue(
        self,
        *,
        request_id: str,
        owner: str,
        stage_id: str,
        task_run_id: str | None = None,
        ttl_seconds: int = 60,
        now: datetime | None = None,
    ) -> int:
        if ttl_seconds < 1:
            raise ValueError("LLM slot waiter TTL must be positive")
        queued_at = now or _now()
        expires_at = queued_at + timedelta(seconds=ttl_seconds)
        with _immediate(self.connection):
            row = self.connection.execute(
                "SELECT queue_position,owner FROM llm_slot_waiters WHERE request_id=?",
                (request_id,),
            ).fetchone()
            if row is not None:
                if str(row["owner"]) != owner:
                    raise ValueError(f"LLM slot request owner mismatch: {request_id}")
                return int(row["queue_position"])
            cursor = self.connection.execute(
                """INSERT INTO llm_slot_waiters(
                       request_id,owner,task_run_id,stage_id,state,enqueued_at,
                       heartbeat_at,expires_at
                   ) VALUES (?,?,?,?, 'queued', ?,?,?)""",
                (
                    request_id,
                    owner,
                    task_run_id,
                    stage_id,
                    _stamp(queued_at),
                    _stamp(queued_at),
                    _stamp(expires_at),
                ),
            )
            assert cursor.lastrowid is not None
            return int(cursor.lastrowid)

    def try_acquire(
        self,
        *,
        request_id: str,
        owner: str,
        capacity: int = 4,
        ttl_seconds: int = 60,
        now: datetime | None = None,
    ) -> LlmSlotLease | None:
        if capacity < 1:
            raise ValueError("LLM slot capacity must be positive")
        if ttl_seconds < 1:
            raise ValueError("LLM slot lease TTL must be positive")
        current = now or _now()
        with _immediate(self.connection):
            self._reap_expired_locked(current)
            waiter = self.connection.execute(
                """SELECT queue_position,request_id,owner,task_run_id,stage_id,state,enqueued_at
                   FROM llm_slot_waiters WHERE request_id=?""",
                (request_id,),
            ).fetchone()
            if waiter is None:
                raise KeyError(f"LLM slot waiter not found: {request_id}")
            if str(waiter["owner"]) != owner:
                raise ValueError(f"LLM slot request owner mismatch: {request_id}")

            if str(waiter["state"]) == "granted":
                lease = self.connection.execute(
                    "SELECT * FROM llm_slot_leases WHERE request_id=? AND owner=?",
                    (request_id, owner),
                ).fetchone()
                if lease is None:
                    raise LlmSlotLeaseLostError(f"LLM slot lease lost: {request_id}")
                return self._lease(waiter, lease)
            if str(waiter["state"]) != "queued":
                raise LlmSlotLeaseLostError(
                    f"LLM slot request is no longer eligible: {request_id}"
                )

            self.connection.execute(
                """UPDATE llm_slot_waiters
                   SET heartbeat_at=?,expires_at=?
                   WHERE request_id=? AND owner=? AND state='queued'""",
                (
                    _stamp(current),
                    _stamp(current + timedelta(seconds=ttl_seconds)),
                    request_id,
                    owner,
                ),
            )

            first = self.connection.execute(
                """SELECT request_id FROM llm_slot_waiters
                   WHERE state='queued' ORDER BY queue_position LIMIT 1"""
            ).fetchone()
            if first is None or str(first["request_id"]) != request_id:
                return None
            active = int(
                self.connection.execute("SELECT COUNT(*) FROM llm_slot_leases").fetchone()[0]
            )
            if active >= capacity:
                return None
            occupied = {
                int(row[0])
                for row in self.connection.execute("SELECT slot_number FROM llm_slot_leases")
            }
            slot_number = next(
                (candidate for candidate in range(capacity) if candidate not in occupied), None
            )
            if slot_number is None:
                return None
            expires_at = current + timedelta(seconds=ttl_seconds)
            self.connection.execute(
                """INSERT INTO llm_slot_leases(
                       slot_number,request_id,owner,task_run_id,stage_id,
                       acquired_at,heartbeat_at,expires_at
                   ) VALUES (?,?,?,?,?,?,?,?)""",
                (
                    slot_number,
                    request_id,
                    owner,
                    waiter["task_run_id"],
                    waiter["stage_id"],
                    _stamp(current),
                    _stamp(current),
                    _stamp(expires_at),
                ),
            )
            self.connection.execute(
                """UPDATE llm_slot_waiters SET state='granted',granted_at=?
                   WHERE request_id=? AND state='queued'""",
                (_stamp(current), request_id),
            )
            lease = self.connection.execute(
                "SELECT * FROM llm_slot_leases WHERE request_id=?", (request_id,)
            ).fetchone()
            assert lease is not None
            return self._lease(waiter, lease)

    def heartbeat(
        self,
        lease: LlmSlotLease,
        *,
        ttl_seconds: int = 60,
        now: datetime | None = None,
    ) -> LlmSlotLease:
        if ttl_seconds < 1:
            raise ValueError("LLM slot lease TTL must be positive")
        current = now or _now()
        expires_at = current + timedelta(seconds=ttl_seconds)
        with _immediate(self.connection):
            cursor = self.connection.execute(
                """UPDATE llm_slot_leases
                   SET heartbeat_at=?,expires_at=?,row_version=row_version+1
                   WHERE slot_number=? AND request_id=? AND owner=? AND expires_at>?""",
                (
                    _stamp(current),
                    _stamp(expires_at),
                    lease.slot_number,
                    lease.request_id,
                    lease.owner,
                    _stamp(current),
                ),
            )
            if cursor.rowcount != 1:
                self._reap_expired_locked(current)
                raise LlmSlotLeaseLostError(f"LLM slot lease lost: {lease.request_id}")
        return LlmSlotLease(
            slot_number=lease.slot_number,
            request_id=lease.request_id,
            owner=lease.owner,
            task_run_id=lease.task_run_id,
            stage_id=lease.stage_id,
            acquired_at=lease.acquired_at,
            expires_at=expires_at,
            queue_position=lease.queue_position,
            enqueued_at=lease.enqueued_at,
        )

    def release(
        self, lease: LlmSlotLease, *, now: datetime | None = None
    ) -> bool:
        current = now or _now()
        with _immediate(self.connection):
            cursor = self.connection.execute(
                """DELETE FROM llm_slot_leases
                   WHERE slot_number=? AND request_id=? AND owner=?""",
                (lease.slot_number, lease.request_id, lease.owner),
            )
            if cursor.rowcount == 1:
                self.connection.execute(
                    """UPDATE llm_slot_waiters SET state='released',finished_at=?
                       WHERE request_id=? AND owner=? AND state='granted'""",
                    (_stamp(current), lease.request_id, lease.owner),
                )
                return True
            return False

    def cancel_waiter(
        self, *, request_id: str, owner: str, now: datetime | None = None
    ) -> bool:
        current = now or _now()
        with _immediate(self.connection):
            cursor = self.connection.execute(
                """UPDATE llm_slot_waiters SET state='canceled',finished_at=?
                   WHERE request_id=? AND owner=? AND state='queued'""",
                (_stamp(current), request_id, owner),
            )
            return cursor.rowcount == 1

    def reap_expired(self, *, now: datetime | None = None) -> int:
        current = now or _now()
        with _immediate(self.connection):
            return self._reap_expired_locked(current)

    def snapshot(self, *, capacity: int = 4, now: datetime | None = None) -> LlmSlotSnapshot:
        current = now or _now()
        with _immediate(self.connection):
            reclaimed = self._reap_expired_locked(current)
            active = int(
                self.connection.execute("SELECT COUNT(*) FROM llm_slot_leases").fetchone()[0]
            )
            waiting = int(
                self.connection.execute(
                    "SELECT COUNT(*) FROM llm_slot_waiters WHERE state='queued'"
                ).fetchone()[0]
            )
        return LlmSlotSnapshot(capacity, active, waiting, reclaimed)

    def _reap_expired_locked(self, now: datetime) -> int:
        expired = [
            str(row[0])
            for row in self.connection.execute(
                "SELECT request_id FROM llm_slot_leases WHERE expires_at<=?",
                (_stamp(now),),
            )
        ]
        if expired:
            placeholders = ",".join("?" for _ in expired)
            self.connection.execute(
                f"DELETE FROM llm_slot_leases WHERE request_id IN ({placeholders})", expired
            )
            self.connection.execute(
                f"""UPDATE llm_slot_waiters SET state='expired',finished_at=?
                    WHERE request_id IN ({placeholders}) AND state='granted'""",
                (_stamp(now), *expired),
            )
        cursor = self.connection.execute(
            """UPDATE llm_slot_waiters SET state='expired',finished_at=?
               WHERE state='queued' AND expires_at<=?""",
            (_stamp(now), _stamp(now)),
        )
        return len(expired) + cursor.rowcount

    @staticmethod
    def _lease(waiter: sqlite3.Row, row: sqlite3.Row) -> LlmSlotLease:
        return LlmSlotLease(
            slot_number=int(row["slot_number"]),
            request_id=str(row["request_id"]),
            owner=str(row["owner"]),
            task_run_id=(
                str(row["task_run_id"]) if row["task_run_id"] is not None else None
            ),
            stage_id=str(row["stage_id"]),
            acquired_at=_parse(row["acquired_at"]),
            expires_at=_parse(row["expires_at"]),
            queue_position=int(waiter["queue_position"]),
            enqueued_at=_parse(waiter["enqueued_at"]),
        )
