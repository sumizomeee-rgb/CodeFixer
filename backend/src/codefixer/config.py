from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ServerSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    host: str = "0.0.0.0"
    port: int = Field(default=9522, ge=1, le=65535)


class StorageSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataRoot: str = "./data"


class ExecutionSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: str = "awaitingStart"
    currentModelId: str = "claude-sonnet"
    maxConcurrentTasks: int = Field(default=8, ge=1, le=64)
    maxConcurrentLlmCalls: int = Field(default=4, ge=1, le=64)
    baselineCohortWindowMs: int = Field(default=2000, ge=0, le=10000)
    maxRepairAttempts: int = Field(default=3, ge=1, le=20)


class AppConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schemaVersion: int = 1
    server: ServerSettings = ServerSettings()
    storage: StorageSettings = StorageSettings()
    execution: ExecutionSettings = ExecutionSettings()
    ticketProviders: list[dict[str, Any]] = []
    agentProfiles: list[dict[str, Any]] = []
    knowledgeProviders: list[dict[str, Any]] = []
    executableBindings: dict[str, dict[str, Any]] = {}
    projects: list[dict[str, Any]] = []


class LoadedConfig(BaseModel):
    config: AppConfig
    base_config_path: Path
    data_root: Path
    frontend_dist: Path
    local_config_path: Path | None = None
    secrets_config_path: Path | None = None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def _normalize_legacy_fields(value: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(value)
    execution = result.get("execution")
    if isinstance(execution, dict) and "agentProfileId" in execution:
        normalized = dict(execution)
        normalized["currentModelId"] = normalized.pop("agentProfileId")
        result["execution"] = normalized
    execution = result.get("execution")
    if isinstance(execution, dict):
        normalized = dict(execution)
        normalized.setdefault("maxConcurrentTasks", 8)
        normalized.setdefault("maxConcurrentLlmCalls", 4)
        normalized.setdefault("baselineCohortWindowMs", 2000)
        normalized.setdefault("maxRepairAttempts", 3)
        result["execution"] = normalized
    return result


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"Config root must be an object: {path}")
    return value


def load_config(base_config_path: Path | None = None) -> LoadedConfig:
    repo_root = Path(__file__).resolve().parents[3]
    default_path = base_config_path or Path(os.environ.get("CODEFIXER_CONFIG", repo_root / "config/defaults/codefixer.json"))
    default_path = default_path.resolve()
    merged = _read_json(default_path)
    machine_root = default_path.parent.parent.parent if default_path.parent.name == "defaults" else default_path.parent
    local_path_raw = os.environ.get("CODEFIXER_LOCAL_CONFIG")
    local_path = Path(local_path_raw).resolve() if local_path_raw else (machine_root / ".local/config.json").resolve()
    if local_path.exists():
        merged = _deep_merge(merged, _read_json(local_path))
    merged = _normalize_legacy_fields(merged)
    secret_path_raw = os.environ.get("CODEFIXER_SECRET_CONFIG")
    secret_path = Path(secret_path_raw).resolve() if secret_path_raw else (machine_root / ".local/secrets.json").resolve()
    config = AppConfig.model_validate(merged)
    data_root_override = os.environ.get("CODEFIXER_DATA_ROOT")
    raw_data_root = Path(data_root_override or config.storage.dataRoot)
    data_root = raw_data_root.resolve() if raw_data_root.is_absolute() else (default_path.parent / raw_data_root).resolve()
    frontend_dist_raw = os.environ.get("CODEFIXER_FRONTEND_DIST")
    frontend_dist = Path(frontend_dist_raw).resolve() if frontend_dist_raw else (repo_root / "frontend/dist").resolve()
    return LoadedConfig(config=config, base_config_path=default_path, data_root=data_root, frontend_dist=frontend_dist, local_config_path=local_path, secrets_config_path=secret_path)
