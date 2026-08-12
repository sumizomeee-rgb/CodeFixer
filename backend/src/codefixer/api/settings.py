from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from codefixer.api.common import config_store, require_if_match
from codefixer.config import AppConfig
from codefixer.infrastructure.database import connect_database
from codefixer.infrastructure.task_store import TaskStore

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ExecutionModeBody(BaseModel):
    mode: Literal["automatic", "awaitingStart"]


@router.get("")
def get_settings(request: Request, response: Response) -> dict[str, object]:
    store = config_store(request)
    response.headers["ETag"] = f'"{store.etag}"'
    return {"config": store.loaded.config.model_dump(mode="json"), "secrets": store.list_secrets(), "etag": store.etag}


@router.put("")
def update_settings(body: AppConfig, request: Request, response: Response) -> dict[str, object]:
    store = config_store(request)
    require_if_match(request, store)
    store.replace_effective(body)
    request.app.state.loaded_config = store.loaded
    response.headers["ETag"] = f'"{store.etag}"'
    return {"config": store.loaded.config.model_dump(mode="json"), "secrets": store.list_secrets(), "etag": store.etag}


@router.put("/execution-mode")
def update_execution_mode(body: ExecutionModeBody, request: Request, response: Response) -> dict[str, object]:
    store = config_store(request)
    require_if_match(request, store)
    previous = store.loaded.config.execution.mode
    store.set_execution_mode(body.mode)
    request.app.state.loaded_config = store.loaded
    activated = 0
    if previous != "automatic" and body.mode == "automatic":
        connection = connect_database(request.app.state.db_path)
        try:
            tasks = TaskStore(connection)
            for task in tasks.list_tasks("awaiting_start"):
                try:
                    tasks.start_task(str(task["id"]), "automatic")
                    activated += 1
                except ValueError:
                    # A task can become unroutable/ineligible between list and activation.
                    # It stays awaiting_start instead of being guessed into execution.
                    continue
        finally:
            connection.close()
    response.headers["ETag"] = f'"{store.etag}"'
    return {"mode": store.loaded.config.execution.mode, "etag": store.etag, "activatedTasks": activated}
