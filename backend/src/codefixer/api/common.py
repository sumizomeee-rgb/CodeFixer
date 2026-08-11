from __future__ import annotations

from fastapi import HTTPException, Request

from codefixer.infrastructure.config_store import ConfigStore


def config_store(request: Request) -> ConfigStore:
    return request.app.state.config_store


def require_if_match(request: Request, store: ConfigStore) -> None:
    raw = request.headers.get("if-match")
    if raw is None:
        raise HTTPException(status_code=428, detail={"code": "precondition_required", "message": "写操作需要 If-Match"})
    actual = raw.strip().strip('"')
    if actual != store.etag:
        raise HTTPException(status_code=409, detail={"code": "config_version_conflict", "message": "配置已被更新，请刷新后重试", "currentEtag": store.etag})
