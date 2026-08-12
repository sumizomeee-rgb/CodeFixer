from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

from codefixer.api.common import config_store, require_if_match
from codefixer.config import AppConfig

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
    store.set_execution_mode(body.mode)
    request.app.state.loaded_config = store.loaded
    response.headers["ETag"] = f'"{store.etag}"'
    return {"mode": store.loaded.config.execution.mode, "etag": store.etag}
