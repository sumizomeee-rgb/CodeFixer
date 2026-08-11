from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from codefixer.config import AppConfig, LoadedConfig, load_config


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def config_etag(config: AppConfig) -> str:
    digest = hashlib.sha256(canonical_json(config.model_dump(mode="json")).encode("utf-8")).hexdigest()
    return digest


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return value


def _deep_diff(base: Any, value: Any) -> Any:
    if isinstance(base, dict) and isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if key not in base:
                result[key] = child
                continue
            diff = _deep_diff(base[key], child)
            if diff is not None:
                result[key] = diff
        return result or None
    return None if base == value else value


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


class ConfigStore:
    def __init__(self, loaded: LoadedConfig):
        self._base_path = loaded.base_config_path
        self._local_path = loaded.local_config_path or self._default_local_path(loaded.base_config_path)
        self._secrets_path = loaded.secrets_config_path or self._default_secrets_path(loaded.base_config_path)
        self._loaded = loaded

    @staticmethod
    def _config_root(base_path: Path) -> Path:
        return base_path.parent.parent if base_path.parent.name == "defaults" else base_path.parent

    @classmethod
    def _default_local_path(cls, base_path: Path) -> Path:
        return cls._config_root(base_path) / "local.json"

    @classmethod
    def _default_secrets_path(cls, base_path: Path) -> Path:
        return cls._config_root(base_path) / "secrets.json"

    @property
    def loaded(self) -> LoadedConfig:
        return self._loaded

    @property
    def etag(self) -> str:
        return config_etag(self._loaded.config)

    def reload(self) -> LoadedConfig:
        previous_local = os.environ.get("CODEFIXER_LOCAL_CONFIG")
        previous_secret = os.environ.get("CODEFIXER_SECRET_CONFIG")
        try:
            os.environ["CODEFIXER_LOCAL_CONFIG"] = str(self._local_path)
            os.environ["CODEFIXER_SECRET_CONFIG"] = str(self._secrets_path)
            self._loaded = load_config(self._base_path)
        finally:
            if previous_local is None:
                os.environ.pop("CODEFIXER_LOCAL_CONFIG", None)
            else:
                os.environ["CODEFIXER_LOCAL_CONFIG"] = previous_local
            if previous_secret is None:
                os.environ.pop("CODEFIXER_SECRET_CONFIG", None)
            else:
                os.environ["CODEFIXER_SECRET_CONFIG"] = previous_secret
        return self._loaded

    def replace_effective(self, config: AppConfig) -> LoadedConfig:
        base = AppConfig.model_validate(_read_json(self._base_path)).model_dump(mode="json")
        effective = config.model_dump(mode="json")
        override = _deep_diff(base, effective) or {}
        _atomic_json(self._local_path, override)
        return self.reload()

    def set_execution_mode(self, mode: str) -> LoadedConfig:
        payload = self._loaded.config.model_dump(mode="json")
        payload["execution"]["mode"] = mode
        return self.replace_effective(AppConfig.model_validate(payload))

    def create_project(self, project: dict[str, Any]) -> LoadedConfig:
        project_id = str(project.get("id", "")).strip()
        if not project_id:
            raise ValueError("project.id is required")
        if any(str(item.get("id")) == project_id for item in self._loaded.config.projects):
            raise KeyError(project_id)
        payload = self._loaded.config.model_dump(mode="json")
        payload["projects"].append(project)
        return self.replace_effective(AppConfig.model_validate(payload))

    def update_project(self, project_id: str, project: dict[str, Any]) -> LoadedConfig:
        payload = self._loaded.config.model_dump(mode="json")
        items = payload["projects"]
        for index, item in enumerate(items):
            if str(item.get("id")) == project_id:
                updated = dict(project)
                updated["id"] = project_id
                items[index] = updated
                return self.replace_effective(AppConfig.model_validate(payload))
        raise KeyError(project_id)

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        for project in self._loaded.config.projects:
            if str(project.get("id")) == project_id:
                return dict(project)
        return None

    def list_secrets(self) -> dict[str, dict[str, bool]]:
        raw = _read_json(self._secrets_path)
        secrets = raw.get("secrets", {})
        if not isinstance(secrets, dict):
            return {}
        return {str(key): {"configured": bool(value)} for key, value in secrets.items()}

    def set_secret(self, key: str, value: str) -> None:
        if not key or "/" in key or "\\" in key:
            raise ValueError("invalid secret key")
        raw = _read_json(self._secrets_path)
        secrets = raw.setdefault("secrets", {})
        if not isinstance(secrets, dict):
            secrets = {}
            raw["secrets"] = secrets
        secrets[key] = value
        raw["schemaVersion"] = 1
        _atomic_json(self._secrets_path, raw)
