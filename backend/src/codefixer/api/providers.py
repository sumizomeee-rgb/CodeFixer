from __future__ import annotations

from typing import Any
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from codefixer.api.common import config_store, require_if_match
from codefixer.adapters.tickets.factory import build_ticket_provider

router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderWriteBody(BaseModel):
    provider: dict[str, Any]
    secrets: dict[str, str] = Field(default_factory=dict)


def _new_provider_id(store: Any) -> str:
    existing = {str(item.get("id")) for item in store.loaded.config.ticketProviders}
    while True:
        provider_id = f"provider-{uuid4().hex[:12]}"
        if provider_id not in existing:
            return provider_id


def _normalize_provider(raw: dict[str, Any], provider_id: str, existing: dict[str, Any] | None = None) -> dict[str, Any]:
    provider_type = str(raw.get("type", ""))
    name = str(raw.get("name", "")).strip()
    if provider_type not in {"redmine", "tapd"}:
        raise ValueError("反馈源类型无效")
    if not name:
        raise ValueError("反馈源名称不能为空")
    provider = {**(existing or {}), **raw, "id": provider_id, "name": name, "type": provider_type}
    provider.pop("pollIntervalSeconds", None)
    provider.pop("assignee", None)
    prefix = provider_id
    if provider_type == "redmine":
        if not str(provider.get("baseUrl", "")).strip():
            raise ValueError("Redmine 服务地址不能为空")
        provider["apiKeySecretRef"] = str((existing or {}).get("apiKeySecretRef") or f"{prefix}-api-key")
        provider.pop("auth", None)
    else:
        if not str(provider.get("workspaceId", "")).strip():
            raise ValueError("TAPD 工作区 ID 不能为空")
        auth = raw.get("auth") if isinstance(raw.get("auth"), dict) else {}
        old_auth = (existing or {}).get("auth") if isinstance((existing or {}).get("auth"), dict) else {}
        mode = str(auth.get("mode", old_auth.get("mode", "oauth")))
        if mode == "oauth":
            provider["auth"] = {"mode": "oauth", "tokenSecretRef": str(old_auth.get("tokenSecretRef") or f"{prefix}-token")}
        elif mode == "basic":
            provider["auth"] = {
                "mode": "basic",
                "usernameSecretRef": str(old_auth.get("usernameSecretRef") or f"{prefix}-username"),
                "passwordSecretRef": str(old_auth.get("passwordSecretRef") or f"{prefix}-password"),
            }
        else:
            raise ValueError("TAPD 登录方式无效")
        provider.pop("apiKeySecretRef", None)
    return provider


def _save_provider_secrets(store: Any, provider: dict[str, Any], secrets: dict[str, str]) -> None:
    if provider["type"] == "redmine":
        if secrets.get("apiKey"):
            store.set_secret(str(provider["apiKeySecretRef"]), secrets["apiKey"])
        return
    auth = provider["auth"]
    if auth["mode"] == "oauth" and secrets.get("token"):
        store.set_secret(str(auth["tokenSecretRef"]), secrets["token"])
    if auth["mode"] == "basic":
        if secrets.get("username"):
            store.set_secret(str(auth["usernameSecretRef"]), secrets["username"])
        if secrets.get("password"):
            store.set_secret(str(auth["passwordSecretRef"]), secrets["password"])


def _provider_config(request: Request, provider_id: str) -> dict[str, Any]:
    for item in request.app.state.config_store.loaded.config.ticketProviders:
        if str(item.get("id")) == provider_id:
            return dict(item)
    raise HTTPException(
        status_code=404,
        detail={"code": "provider_not_found", "message": f"工单来源不存在：{provider_id}"},
    )


@router.get("")
def list_providers(request: Request) -> dict[str, object]:
    items: list[dict[str, object]] = []
    for raw in request.app.state.config_store.loaded.config.ticketProviders:
        item = dict(raw)
        auth = item.get("auth")
        if isinstance(auth, dict):
            item["auth"] = {
                key: value for key, value in auth.items() if key.endswith("Ref") or key == "mode"
            }
        items.append(item)
    return {"items": items}


@router.post("", status_code=201)
def create_provider(body: ProviderWriteBody, request: Request, response: Response) -> dict[str, object]:
    store = config_store(request)
    require_if_match(request, store)
    try:
        provider = _normalize_provider(body.provider, _new_provider_id(store))
        _save_provider_secrets(store, provider, body.secrets)
        store.create_provider(provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_provider", "message": str(exc)}) from exc
    request.app.state.loaded_config = store.loaded
    response.headers["ETag"] = f'"{store.etag}"'
    return {"provider": provider, "etag": store.etag}


@router.put("/{provider_id}")
def update_provider(provider_id: str, body: ProviderWriteBody, request: Request, response: Response) -> dict[str, object]:
    store = config_store(request)
    require_if_match(request, store)
    existing = _provider_config(request, provider_id)
    try:
        provider = _normalize_provider(body.provider, provider_id, existing)
        _save_provider_secrets(store, provider, body.secrets)
        store.update_provider(provider_id, provider)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_provider", "message": str(exc)}) from exc
    request.app.state.loaded_config = store.loaded
    response.headers["ETag"] = f'"{store.etag}"'
    return {"provider": provider, "etag": store.etag}


@router.post("/{provider_id}/test")
def test_provider(provider_id: str, request: Request) -> dict[str, object]:
    config = _provider_config(request, provider_id)
    try:
        provider = build_ticket_provider(config, request.app.state.config_store.get_secret)
        return provider.test_connection()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "provider_unavailable",
                "message": f"工单来源连接失败：{provider_id}",
                "reason": str(exc),
            },
        ) from exc


@router.get("/{provider_id}/versions")
def list_provider_versions(provider_id: str, request: Request) -> dict[str, object]:
    config = _provider_config(request, provider_id)
    try:
        provider = build_ticket_provider(config, request.app.state.config_store.get_secret)
        return {"providerId": provider_id, "items": provider.list_versions()}
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 429:
            raise HTTPException(
                status_code=429,
                detail={
                    "code": "provider_rate_limited",
                    "message": "TAPD 请求过于频繁，暂时无法加载版本；“全部版本”不受影响，请稍后重试",
                },
            ) from exc
        raise HTTPException(
            status_code=503,
            detail={
                "code": "provider_versions_unavailable",
                "message": f"无法读取反馈源“{config.get('name') or provider_id}”的版本",
                "reason": str(exc),
            },
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "provider_versions_unavailable",
                "message": f"无法读取反馈源“{config.get('name') or provider_id}”的版本",
                "reason": str(exc),
            },
        ) from exc
