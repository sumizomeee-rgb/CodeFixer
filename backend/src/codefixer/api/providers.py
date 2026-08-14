from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from codefixer.adapters.tickets.factory import build_ticket_provider

router = APIRouter(prefix="/api/providers", tags=["providers"])


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
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "provider_versions_unavailable",
                "message": f"无法读取反馈源版本：{provider_id}",
                "reason": str(exc),
            },
        ) from exc
