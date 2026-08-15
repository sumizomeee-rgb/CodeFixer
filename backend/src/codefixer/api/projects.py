from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from codefixer.api.common import config_store, require_if_match
from codefixer.application.services.preflight import normalize_project_configuration, run_project_preflight
from codefixer.infrastructure.database import connect_database
from codefixer.infrastructure.task_store import TaskStore

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectEnabledBody(BaseModel):
    enabled: bool


def _provider_refs(project: dict[str, Any]) -> set[str]:
    return {
        str(rule.get("providerRef") or "").strip()
        for rule in project.get("routingRules") or []
        if isinstance(rule, dict) and str(rule.get("providerRef") or "").strip()
    }


def _new_project_id(store: Any) -> str:
    while True:
        project_id = f"pipeline-{uuid4().hex[:12]}"
        if store.get_project(project_id) is None:
            return project_id


@router.get("")
def list_projects(request: Request, response: Response) -> dict[str, object]:
    store = config_store(request)
    response.headers["ETag"] = f'"{store.etag}"'
    return {"items": store.loaded.config.projects, "etag": store.etag}


@router.post("", status_code=201)
def create_project(project: dict[str, Any], request: Request, response: Response) -> dict[str, object]:
    store = config_store(request)
    require_if_match(request, store)
    try:
        normalized = normalize_project_configuration(
            {
                **project,
                "id": _new_project_id(store),
                "intakeStartedAt": datetime.now(UTC).isoformat(),
            }
        )
        store.create_project(normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_project", "message": str(exc)}) from exc
    except KeyError as exc:
        raise HTTPException(status_code=409, detail={"code": "project_exists", "message": f"项目已存在：{exc.args[0]}"}) from exc
    request.app.state.loaded_config = store.loaded
    response.headers["ETag"] = f'"{store.etag}"'
    return {"project": store.get_project(str(normalized.get("id"))), "etag": store.etag}


@router.put("/{project_id}")
def update_project(project_id: str, project: dict[str, Any], request: Request, response: Response) -> dict[str, object]:
    store = config_store(request)
    require_if_match(request, store)
    if store.get_project(project_id) is None:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": f"项目不存在：{project_id}"})
    try:
        existing = store.get_project(project_id) or {}
        normalized = normalize_project_configuration(
            {
                **project,
                "id": project_id,
                "intakeStartedAt": existing.get("intakeStartedAt")
                or datetime.now(UTC).isoformat(),
            }
        )
        store.update_project(project_id, normalized)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_project", "message": str(exc)}) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": f"项目不存在：{project_id}"}) from exc
    request.app.state.loaded_config = store.loaded
    response.headers["ETag"] = f'"{store.etag}"'
    return {"project": store.get_project(project_id), "etag": store.etag}


@router.put("/{project_id}/enabled")
def set_project_enabled(
    project_id: str,
    body: ProjectEnabledBody,
    request: Request,
    response: Response,
) -> dict[str, object]:
    store = config_store(request)
    require_if_match(request, store)
    existing = store.get_project(project_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "project_not_found", "message": f"项目不存在：{project_id}"},
        )
    was_enabled = existing.get("enabled", True) is not False
    if body.enabled == was_enabled:
        response.headers["ETag"] = f'"{store.etag}"'
        return {"project": existing, "etag": store.etag}

    changed_at = datetime.now(UTC).isoformat()
    updated = {**existing, "enabled": body.enabled}
    if body.enabled:
        updated["intakeStartedAt"] = changed_at

    provider_refs = _provider_refs(existing)
    other_active_refs = {
        provider_ref
        for project in store.loaded.config.projects
        if str(project.get("id")) != project_id and project.get("enabled", True) is not False
        for provider_ref in _provider_refs(project)
    }
    store.update_project(project_id, updated)
    if body.enabled:
        with connect_database(request.app.state.db_path) as connection:
            cursors = TaskStore(connection)
            for provider_ref in provider_refs - other_active_refs:
                cursors.set_cursor(provider_ref, changed_at)
    request.app.state.loaded_config = store.loaded
    response.headers["ETag"] = f'"{store.etag}"'
    return {"project": store.get_project(project_id), "etag": store.etag}


@router.post("/{project_id}/preflight")
def preflight_project(project_id: str, request: Request) -> dict[str, object]:
    store = config_store(request)
    project = store.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail={"code": "project_not_found", "message": f"项目不存在：{project_id}"})
    return run_project_preflight(store.loaded, project)
