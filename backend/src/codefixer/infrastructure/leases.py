from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta


class LeaseBusyError(RuntimeError):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def _stamp(value: datetime) -> str:
    return value.isoformat()


class LeaseStore:
    def __init__(self, connection: sqlite3.Connection):
        self.connection = connection

    def acquire(self, resource_key: str, owner: str, ttl_seconds: int = 300) -> None:
        now = _now()
        expires = now + timedelta(seconds=ttl_seconds)
        with self.connection:
            row = self.connection.execute(
                "SELECT owner,expires_at,row_version FROM worker_leases WHERE resource_key=?",
                (resource_key,),
            ).fetchone()
            if row is not None:
                current_owner = str(row["owner"])
                current_expiry = datetime.fromisoformat(str(row["expires_at"]))
                if current_expiry > now and current_owner != owner:
                    raise LeaseBusyError(f"resource lease busy: {resource_key}")
                self.connection.execute(
                    """UPDATE worker_leases SET owner=?,expires_at=?,heartbeat_at=?,
                       row_version=row_version+1 WHERE resource_key=?""",
                    (owner, _stamp(expires), _stamp(now), resource_key),
                )
            else:
                self.connection.execute(
                    """INSERT INTO worker_leases(resource_key,owner,expires_at,heartbeat_at)
                       VALUES (?,?,?,?)""",
                    (resource_key, owner, _stamp(expires), _stamp(now)),
                )

    def heartbeat(self, resource_key: str, owner: str, ttl_seconds: int = 300) -> None:
        now = _now()
        with self.connection:
            cursor = self.connection.execute(
                """UPDATE worker_leases SET expires_at=?,heartbeat_at=?,row_version=row_version+1
                   WHERE resource_key=? AND owner=?""",
                (_stamp(now + timedelta(seconds=ttl_seconds)), _stamp(now), resource_key, owner),
            )
            if cursor.rowcount != 1:
                raise LeaseBusyError(f"lease ownership lost: {resource_key}")

    def release(self, resource_key: str, owner: str) -> None:
        with self.connection:
            self.connection.execute(
                "DELETE FROM worker_leases WHERE resource_key=? AND owner=?",
                (resource_key, owner),
            )
