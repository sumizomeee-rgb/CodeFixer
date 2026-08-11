from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"


def connect_database(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=10, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def apply_migrations(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    applied = {
        int(row[0])
        for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version")
    }
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = int(path.name.split("_", 1)[0])
        if version in applied:
            continue
        sql = path.read_text(encoding="utf-8")
        with connection:
            connection.executescript(sql)
            connection.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))


def initialize_database(data_root: Path) -> Path:
    db_path = data_root / "codefixer.db"
    with connect_database(db_path) as connection:
        apply_migrations(connection)
    return db_path


def inspect_database(db_path: Path) -> dict[str, object]:
    if not db_path.exists():
        return {"ready": False, "reason": "database_missing"}
    with connect_database(db_path) as connection:
        journal = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        migration_count = int(
            connection.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]
        )
    return {
        "ready": journal == "wal" and migration_count >= 1,
        "journalMode": journal,
        "migrationCount": migration_count,
    }
