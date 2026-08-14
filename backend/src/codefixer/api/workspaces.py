from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, model_validator

from codefixer.application.services.workspace_detection import detect_workspace


router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


class DetectWorkspaceBody(BaseModel):
    locationType: Literal["local", "remote"] | None = None
    location: str | None = None
    path: str | None = None

    @model_validator(mode="after")
    def validate_location(self) -> DetectWorkspaceBody:
        if not (self.location or self.path or "").strip():
            raise ValueError("location 或 path 至少需要填写一个")
        return self


class WorkspaceCheckResponse(BaseModel):
    id: str
    status: Literal["ready", "warning", "failed"]
    summary: str
    detail: str | None = None


class WorkspaceDetectionResponse(BaseModel):
    locationType: Literal["local", "remote"]
    location: str
    ready: bool
    vcsKind: Literal["git", "svn", "unknown"]
    hostingKind: Literal["gitlab", "github", "other", "none", "ambiguous"]
    repositoryRoot: str | None = None
    remoteUrl: str | None = None
    webBaseUrl: str | None = None
    summary: str
    checks: list[WorkspaceCheckResponse]
    path: str | None = None


class BrowseDirectoriesBody(BaseModel):
    path: str | None = None


class DirectoryItem(BaseModel):
    name: str
    path: str


class DirectoryListingResponse(BaseModel):
    path: str | None
    parent: str | None
    items: list[DirectoryItem]
    truncated: bool = False


@router.post("/detect", response_model=WorkspaceDetectionResponse, response_model_exclude_none=True)
def detect_workspace_route(body: DetectWorkspaceBody) -> dict[str, object]:
    legacy_request = body.location is None and body.path is not None
    location = (body.location or body.path or "").strip()
    result = detect_workspace(location, location_type=body.locationType or "local")
    if legacy_request:
        result["path"] = result["location"]
    return result


def _filesystem_roots() -> list[Path]:
    if os.name != "nt":
        return [Path("/")]
    roots: list[Path] = []
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        candidate = Path(f"{letter}:\\")
        if candidate.is_dir():
            roots.append(candidate)
    return roots


@router.post("/browse", response_model=DirectoryListingResponse)
def browse_directories(body: BrowseDirectoriesBody) -> dict[str, object]:
    """只列出一层真实目录，不读取文件，也不跟随目录符号链接。"""

    if body.path is None or not body.path.strip():
        roots = _filesystem_roots()
        return {
            "path": None,
            "parent": None,
            "items": [{"name": str(root), "path": str(root)} for root in roots],
            "truncated": False,
        }
    candidate = Path(os.path.expandvars(os.path.expanduser(body.path.strip())))
    if not candidate.is_absolute():
        raise HTTPException(status_code=422, detail={"code": "absolute_path_required", "message": "目录浏览只接受绝对路径"})
    path = candidate.resolve(strict=False)
    if not path.is_dir():
        raise HTTPException(status_code=404, detail={"code": "directory_not_found", "message": "目录不存在或不可读取"})
    try:
        children = sorted(
            (child for child in path.iterdir() if child.is_dir() and not child.is_symlink()),
            key=lambda value: value.name.casefold(),
        )
    except OSError as exc:
        raise HTTPException(status_code=403, detail={"code": "directory_unreadable", "message": "当前服务进程无权读取该目录"}) from exc
    limit = 200
    parent = path.parent if path.parent != path else None
    return {
        "path": str(path),
        "parent": str(parent) if parent is not None else None,
        "items": [{"name": child.name, "path": str(child)} for child in children[:limit]],
        "truncated": len(children) > limit,
    }
