from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from codefixer import __version__
from codefixer.infrastructure.database import inspect_database
from codefixer.infrastructure.dependency_checks import inspect_executable_dependencies

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
def health() -> dict[str, object]:
    return {"status": "ok", "service": "codefixer", "version": __version__}


def _writable_directory(path: Path) -> tuple[bool, str | None]:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".codefixer-write-probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, None
    except OSError as exc:
        return False, str(exc)


@router.get("/readiness")
def readiness(request: Request) -> dict[str, object]:
    loaded = request.app.state.loaded_config
    db_path: Path = request.app.state.db_path
    writable, writable_reason = _writable_directory(loaded.data_root)
    db = inspect_database(db_path)
    frontend_ready = (loaded.frontend_dist / "index.html").is_file()
    checks: list[dict[str, Any]] = [
        {"id": "config.loaded", "status": "ready", "summary": "配置已加载", "detail": str(loaded.base_config_path)},
        {"id": "storage.data_root", "status": "ready" if writable else "failed", "summary": "数据目录可写" if writable else "数据目录不可写", "detail": str(loaded.data_root) if writable else writable_reason},
        {"id": "sqlite.wal", "status": "ready" if bool(db.get("ready")) else "failed", "summary": "SQLite WAL 可用" if bool(db.get("ready")) else "SQLite WAL 不可用", "detail": db},
        {"id": "frontend.dist", "status": "ready" if frontend_ready else "failed", "summary": "Web 构建产物存在" if frontend_ready else "Web 构建产物缺失", "detail": str(loaded.frontend_dist)},
        *inspect_executable_dependencies(loaded),
    ]
    failed = any(item["status"] == "failed" for item in checks)
    warning = any(item["status"] == "warning" for item in checks)
    return {"status": "not_ready" if failed else ("warning" if warning else "ready"), "ready": not failed, "checks": checks, "environment": os.environ.get("CODEFIXER_ENV", "development")}


@router.get("/dashboard")
def dashboard(request: Request) -> dict[str, object]:
    from codefixer.infrastructure.database import connect_database
    from codefixer.infrastructure.task_store import TaskStore

    connection = connect_database(request.app.state.db_path)
    try:
        counts = {str(row["status"]): int(row["count"]) for row in connection.execute("SELECT status,COUNT(*) AS count FROM tasks GROUP BY status").fetchall()}
        results = {str(row["result"]): int(row["count"]) for row in connection.execute("SELECT result,COUNT(*) AS count FROM tasks WHERE result IS NOT NULL GROUP BY result").fetchall()}
        tasks = TaskStore(connection)
        recent = tasks.list_tasks()[:8]
        attention = [item for item in recent if item["status"] in {"failed", "cancel_requested"}]
        active = sum(counts.get(status, 0) for status in ("queued", "running", "cancel_requested"))
        return {"metrics": {"active": active, "queued": counts.get("queued", 0), "running": counts.get("running", 0), "completedChanged": results.get("changed", 0), "completedNoChange": results.get("no_change", 0), "failed": counts.get("failed", 0)}, "recentTasks": recent, "attention": attention}
    finally:
        connection.close()
