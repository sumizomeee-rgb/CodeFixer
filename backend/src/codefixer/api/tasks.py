from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request

from codefixer.infrastructure.database import connect_database
from codefixer.infrastructure.task_store import TaskStore
from codefixer.application.services.localization_apply import apply_frozen_change_to_localization

router = APIRouter(prefix='/api/tasks', tags=['tasks'])


def _artifact_payload(data_root: Path, relative_path: object) -> dict[str, object] | None:
    try:
        target = (data_root / str(relative_path)).resolve()
        target.relative_to(data_root.resolve())
        if not target.is_file() or target.stat().st_size > 2 * 1024 * 1024:
            return None
        value = json.loads(target.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else None
    except (OSError, ValueError, json.JSONDecodeError):
        return None


def _enrich_task_artifacts(task: dict[str, object], data_root: Path) -> dict[str, object]:
    for raw_run in task.get('runs') or []:
        if not isinstance(raw_run, dict):
            continue
        by_type = {str(item.get('artifact_type')): item for item in raw_run.get('artifacts') or [] if isinstance(item, dict)}
        for artifact_type, field in (
            ('task_conclusion', 'conclusion'),
            ('change_manifest', 'change_manifest'),
            ('delivery_metadata', 'delivery_metadata'),
            ('verification', 'verification'),
        ):
            item = by_type.get(artifact_type)
            if item:
                raw_run[field] = _artifact_payload(data_root, item.get('relative_path'))
    return task


def _store(request: Request) -> tuple[TaskStore, sqlite3.Connection]:
    connection = connect_database(request.app.state.db_path)
    return TaskStore(connection), connection


@router.get('')
def list_tasks(request: Request, status: str | None = Query(default=None)) -> dict[str, object]:
    store, connection = _store(request)
    try:
        return {'items': store.list_tasks(status)}
    finally:
        connection.close()


@router.get('/{task_id}')
def get_task(task_id: str, request: Request) -> dict[str, object]:
    store, connection = _store(request)
    try:
        try:
            return _enrich_task_artifacts(store.get_task(task_id), request.app.state.config_store.loaded.data_root)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={'code':'task_not_found','message':f'任务不存在：{task_id}'}) from exc
    finally:
        connection.close()


@router.post('/{task_id}/start')
def start_task(task_id: str, request: Request) -> dict[str, object]:
    store, connection = _store(request)
    try:
        try:
            mode = request.app.state.config_store.loaded.config.execution.mode
            return store.start_task(task_id, mode)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={'code':'task_not_found','message':f'任务不存在：{task_id}'}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={'code':'invalid_task_transition','message':str(exc)}) from exc
    finally:
        connection.close()


@router.post('/{task_id}/retry-delivery')
def retry_delivery(task_id: str, request: Request) -> dict[str, object]:
    store, connection = _store(request)
    try:
        try:
            task = store.get_task(task_id)
            run_id = str(task.get('current_run_id') or '')
            if not run_id:
                raise ValueError('task has no current run')
            run_root = request.app.state.config_store.loaded.data_root / 'tasks' / task_id / 'runs' / run_id
            manifest = run_root / 'freeze-change' / 'change-manifest.json'
            config_snapshot = run_root / 'snapshot' / 'config-snapshot.json'
            if not manifest.is_file() or not config_snapshot.is_file():
                raise ValueError('task has no frozen change; start a new TaskRun instead')
            return store.retry_frozen_delivery(task_id, run_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={'code':'task_not_found','message':f'任务不存在：{task_id}'}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={'code':'delivery_retry_unavailable','message':str(exc)}) from exc
    finally:
        connection.close()


@router.post('/{task_id}/cancel')
def cancel_task(task_id: str, request: Request) -> dict[str, object]:
    store, connection = _store(request)
    try:
        try:
            return store.cancel_task(task_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={'code':'task_not_found','message':f'任务不存在：{task_id}'}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail={'code':'invalid_task_transition','message':str(exc)}) from exc
    finally:
        connection.close()


@router.post('/{task_id}/apply-to-localization')
def apply_to_localization(task_id: str, request: Request) -> dict[str, object]:
    store, connection = _store(request)
    try:
        try:
            task = store.get_task(task_id)
            project_id = str(task.get('project_id') or '')
            project = next(
                (dict(item) for item in request.app.state.config_store.loaded.config.projects if str(item.get('id') or '') == project_id),
                None,
            )
            if project is None:
                raise ValueError('任务所属流水线已不存在')
            result = apply_frozen_change_to_localization(
                task=task,
                data_root=request.app.state.config_store.loaded.data_root,
                current_project=project,
            )
            return {
                'target': str(result.target),
                'copied': result.copied,
                'deleted': result.deleted,
            }
        except KeyError as exc:
            raise HTTPException(status_code=404, detail={'code':'task_not_found','message':f'任务不存在：{task_id}'}) from exc
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=409, detail={'code':'localization_apply_unavailable','message':str(exc)}) from exc
    finally:
        connection.close()
