from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def _envelope(code: str, message: str, details: Any = None) -> dict[str, object]:
    error: dict[str, Any] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"data": None, "meta": {"timestamp": datetime.now(UTC).isoformat()}, "error": error}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        if isinstance(exc.detail, dict):
            code = str(exc.detail.get("code", "http_error"))
            message = str(exc.detail.get("message", "请求失败"))
            details = {k: v for k, v in exc.detail.items() if k not in {"code", "message"}} or None
        else:
            code = "http_error"
            message = str(exc.detail)
            details = None
        return JSONResponse(status_code=exc.status_code, content=_envelope(code, message, details), headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content=_envelope("validation_error", "请求参数校验失败", exc.errors()))
