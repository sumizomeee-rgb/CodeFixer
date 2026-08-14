from __future__ import annotations

from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from codefixer.api.errors import install_error_handlers
from codefixer.api.projects import router as projects_router
from codefixer.api.providers import router as providers_router
from codefixer.api.secrets import router as secrets_router
from codefixer.api.settings import router as settings_router
from codefixer.api.system import router as system_router
from codefixer.api.tasks import router as tasks_router
from codefixer.api.workspaces import router as workspaces_router
from codefixer.config import LoadedConfig, load_config
from codefixer.infrastructure.config_store import ConfigStore
from codefixer.infrastructure.database import initialize_database
from codefixer.orchestration.scheduler import Scheduler


def create_app(loaded_config: LoadedConfig | None = None, *, start_background: bool | None = None) -> FastAPI:
    loaded = loaded_config or load_config()
    background_enabled = (loaded_config is None) if start_background is None else start_background
    if os.environ.get("CODEFIXER_DISABLE_BACKGROUND", "").strip().lower() in {"1", "true", "yes"}:
        background_enabled = False

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loaded.data_root.mkdir(parents=True, exist_ok=True)
        app.state.db_path = initialize_database(loaded.data_root)
        scheduler = None
        if background_enabled:
            contracts_root = Path(__file__).resolve().parents[3] / "contracts"
            scheduler = Scheduler(db_path=app.state.db_path, config_store=app.state.config_store, contracts_root=contracts_root)
            app.state.scheduler = scheduler
            scheduler.start()
        try:
            yield
        finally:
            if scheduler is not None:
                await scheduler.stop()

    app = FastAPI(title="CodeFixer API", version="0.1.0", lifespan=lifespan)
    install_error_handlers(app)
    app.state.loaded_config = loaded
    app.state.config_store = ConfigStore(loaded)
    app.include_router(system_router)
    app.include_router(settings_router)
    app.include_router(projects_router)
    app.include_router(providers_router)
    app.include_router(secrets_router)
    app.include_router(tasks_router)
    app.include_router(workspaces_router)

    assets = loaded.frontend_dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")
        candidate = (loaded.frontend_dist / full_path).resolve()
        try:
            candidate.relative_to(loaded.frontend_dist)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = loaded.frontend_dist / "index.html"
        if not index.is_file():
            raise HTTPException(status_code=503, detail="Frontend build is unavailable")
        return FileResponse(index, headers={"Cache-Control": "no-store"})

    return app


app = create_app()
