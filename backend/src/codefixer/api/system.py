from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Request

from codefixer import __version__
from codefixer.infrastructure.database import inspect_database

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

    checks = [
        {
            "id": "config.loaded",
            "status": "ready",
            "detail": str(loaded.base_config_path),
        },
        {
            "id": "storage.data_root",
            "status": "ready" if writable else "failed",
            "detail": str(loaded.data_root) if writable else writable_reason,
        },
        {
            "id": "sqlite.wal",
            "status": "ready" if bool(db.get("ready")) else "failed",
            "detail": db,
        },
        {
            "id": "frontend.dist",
            "status": "ready" if frontend_ready else "failed",
            "detail": str(loaded.frontend_dist),
        },
    ]
    ready = all(item["status"] == "ready" for item in checks)
    return {
        "status": "ready" if ready else "not_ready",
        "ready": ready,
        "checks": checks,
        "environment": os.environ.get("CODEFIXER_ENV", "development"),
    }
