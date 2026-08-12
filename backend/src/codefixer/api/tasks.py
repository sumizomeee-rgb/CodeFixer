from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query, Request

from codefixer.infrastructure.database import connect_database
from codefixer.infrastructure.task_store import TaskStore

router = APIRouter(prefix='/api/tasks', tags=['tasks'])


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
            return store.get_task(task_id)
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
