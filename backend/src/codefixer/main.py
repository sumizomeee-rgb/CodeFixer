from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from codefixer.api.system import router as system_router
from codefixer.config import LoadedConfig, load_config
from codefixer.infrastructure.database import initialize_database


def create_app(loaded_config: LoadedConfig | None = None) -> FastAPI:
    loaded = loaded_config or load_config()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        loaded.data_root.mkdir(parents=True, exist_ok=True)
        app.state.db_path = initialize_database(loaded.data_root)
        yield

    app = FastAPI(title="CodeFixer API", version="0.1.0", lifespan=lifespan)
    app.state.loaded_config = loaded
    app.include_router(system_router)

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
        return FileResponse(index)

    return app


app = create_app()
