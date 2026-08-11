from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from codefixer.api.common import config_store

router = APIRouter(prefix="/api/secrets", tags=["secrets"])


class SecretBody(BaseModel):
    value: str = Field(min_length=1)


@router.get("")
def list_secrets(request: Request) -> dict[str, object]:
    return {"items": config_store(request).list_secrets()}


@router.put("/{key}")
def set_secret(key: str, body: SecretBody, request: Request) -> dict[str, object]:
    store = config_store(request)
    store.set_secret(key, body.value)
    return {"key": key, "configured": True}
