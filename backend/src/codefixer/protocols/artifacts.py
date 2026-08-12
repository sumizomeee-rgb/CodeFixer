from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class ArtifactProtocolError(ValueError):
    """Raised when an artifact violates a CodeFixer protocol contract."""


@dataclass(frozen=True)
class StoredArtifact:
    path: Path
    sha256: str
    size_bytes: int


class SchemaRegistry:
    def __init__(self, contracts_root: Path):
        self.contracts_root = contracts_root.resolve()

    def schema_path(self, name: str) -> Path:
        candidate = (self.contracts_root / "artifacts" / f"{name}.schema.json").resolve()
        try:
            candidate.relative_to(self.contracts_root)
        except ValueError as exc:
            raise ArtifactProtocolError(f"invalid schema name: {name}") from exc
        if not candidate.is_file():
            raise ArtifactProtocolError(f"artifact schema not found: {name}")
        return candidate

    def load(self, name: str) -> dict[str, Any]:
        payload = json.loads(self.schema_path(name).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ArtifactProtocolError(f"schema root must be object: {name}")
        return payload

    def validate(self, name: str, payload: dict[str, Any]) -> None:
        schema = self.load(name)
        errors = sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda item: list(item.path))
        if errors:
            details = "; ".join(error.message for error in errors[:4])
            raise ArtifactProtocolError(f"{name} is invalid: {details}")


class ArtifactStore:
    def __init__(self, data_root: Path, schema_registry: SchemaRegistry):
        self.data_root = data_root.resolve()
        self.schema_registry = schema_registry

    def task_root(self, task_id: str) -> Path:
        return self._safe(self.data_root / "tasks" / task_id)

    def run_root(self, task_id: str, run_id: str) -> Path:
        return self._safe(self.task_root(task_id) / "runs" / run_id)

    def stage_root(self, task_id: str, run_id: str, stage: str, attempt: int | None = None) -> Path:
        root = self.run_root(task_id, run_id) / "stages" / stage
        if attempt is not None:
            root /= str(attempt)
        return self._safe(root)

    def write_bytes(self, path: Path, content: bytes) -> StoredArtifact:
        target = self._safe(path)
        self._atomic_bytes(target, content)
        return self.describe(target)

    def write_text(self, path: Path, content: str) -> StoredArtifact:
        return self.write_bytes(path, content.encode("utf-8"))

    def write_json(
        self,
        path: Path,
        payload: dict[str, Any],
        *,
        schema_name: str | None = None,
        copy_schema: bool = False,
    ) -> StoredArtifact:
        if schema_name is not None:
            self.schema_registry.validate(schema_name, payload)
        encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        target = self._safe(path)
        self._atomic_bytes(target, encoded)
        if schema_name is not None and copy_schema:
            schema_target = target.with_suffix(".schema.json")
            self._atomic_bytes(schema_target, self.schema_registry.schema_path(schema_name).read_bytes())
        return self.describe(target)

    def describe(self, path: Path) -> StoredArtifact:
        target = self._safe(path)
        data = target.read_bytes()
        return StoredArtifact(target, hashlib.sha256(data).hexdigest(), len(data))

    def _safe(self, path: Path) -> Path:
        target = path.resolve()
        try:
            target.relative_to(self.data_root)
        except ValueError as exc:
            raise ArtifactProtocolError(f"artifact path escapes data root: {path}") from exc
        return target

    @staticmethod
    def _atomic_bytes(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass


@dataclass(frozen=True)
class StageEntry:
    task_id: str
    run_id: str
    stage: str
    attempt: int | None
    inputs: tuple[tuple[str, Path], ...]
    output_path: Path
    schema_path: Path
    notes: tuple[str, ...] = ()


def render_stage_entry(entry: StageEntry) -> str:
    lines = ["# CodeFixer Stage Entry", "", f"- Task: `{entry.task_id}`", f"- Run: `{entry.run_id}`", f"- Stage: `{entry.stage}`"]
    if entry.attempt is not None:
        lines.append(f"- Attempt: `{entry.attempt}`")
    lines.extend(["", "## Required inputs"])
    for label, path in entry.inputs:
        lines.append(f"- {label}: `{path.resolve()}`")
    lines.extend([
        "",
        "## Output contract",
        f"- Write the required JSON result to: `{entry.output_path.resolve()}`",
        f"- It must validate against: `{entry.schema_path.resolve()}`",
        "- Do not create delivery side effects. Do not change repositories outside the authorized workspace.",
    ])
    if entry.notes:
        lines.extend(["", "## Stage constraints", *[f"- {note}" for note in entry.notes]])
    lines.extend(["", "Read the referenced files yourself. Do not assume facts that are not supported by them.", ""])
    return "\n".join(lines)
