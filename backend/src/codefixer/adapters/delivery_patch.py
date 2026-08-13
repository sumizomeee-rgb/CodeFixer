from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

from codefixer.application.ports.delivery import FinalActionResult, FrozenDeliveryContext
from codefixer.infrastructure.config_store import canonical_json
from codefixer.infrastructure.delivery_store import DeliveryStore


@dataclass(frozen=True)
class PatchDeliveryResult:
    status: str
    path: Path
    sha256: str
    adopted_existing: bool


class PatchDeliveryError(RuntimeError):
    pass


def deliver_patch(*, patch_bytes: bytes, expected_sha256: str, output_directory: Path, filename: str, overwrite: bool = False) -> PatchDeliveryResult:
    if Path(filename).name != filename or not filename.endswith(".patch"):
        raise PatchDeliveryError("patch filename must be a safe basename ending in .patch")
    actual = hashlib.sha256(patch_bytes).hexdigest()
    if actual != expected_sha256:
        raise PatchDeliveryError("frozen patch hash mismatch")
    output_directory.mkdir(parents=True, exist_ok=True)
    target = (output_directory / filename).resolve()
    try:
        target.relative_to(output_directory.resolve())
    except ValueError as exc:
        raise PatchDeliveryError("patch target escapes output directory") from exc
    if target.exists() and not overwrite:
        existing = hashlib.sha256(target.read_bytes()).hexdigest()
        if existing == expected_sha256:
            return PatchDeliveryResult("succeeded", target, existing, True)
        raise PatchDeliveryError("patch target exists with different content")
    mode = "wb" if overwrite else "xb"
    with target.open(mode) as handle:
        handle.write(patch_bytes)
        handle.flush()
        os.fsync(handle.fileno())
    return PatchDeliveryResult("succeeded", target, actual, False)


class PatchFinalAction:
    action_type = "patch"

    def __init__(self, *, action_id: str, action_version: int, store: DeliveryStore, output_directory: Path, filename_template: str = "{task_id}-{run_id}.patch", overwrite: bool = False) -> None:
        self.action_id = action_id
        self.action_version = action_version
        self.store = store
        self.output_directory = output_directory
        self.filename_template = filename_template
        self.overwrite = overwrite

    def execute(self, context: FrozenDeliveryContext) -> FinalActionResult:
        config = {"outputDirectory": str(self.output_directory), "filenameTemplate": self.filename_template, "overwrite": self.overwrite}
        config_hash = hashlib.sha256(canonical_json(config).encode()).hexdigest()
        intent_key = hashlib.sha256(f"{context.run_id}:{self.action_id}:{self.action_version}:{config_hash}".encode()).hexdigest()
        action = self.store.ensure_action(task_run_id=context.run_id, action_id=self.action_id, action_version=self.action_version, action_type=self.action_type, config_hash=config_hash, intent_key=intent_key)
        action_db_id = int(action["id"])
        self.store.mark_action(action_db_id, status="running")
        try:
            filename = self.filename_template.format(task_id=context.task_id, run_id=context.run_id, change_version=context.change_version)
            delivered = deliver_patch(patch_bytes=context.patch_path.read_bytes(), expected_sha256=context.patch_sha256, output_directory=self.output_directory, filename=filename, overwrite=self.overwrite)
            detail: dict[str, object] = {"path": str(delivered.path), "sha256": delivered.sha256, "adoptedExisting": delivered.adopted_existing}
            self.store.mark_action(action_db_id, status="succeeded", outcome="success", result=detail)
            return FinalActionResult(self.action_id, self.action_type, "succeeded", "success", detail)
        except Exception as exc:
            detail = {"error": str(exc)}
            self.store.mark_action(action_db_id, status="failed", outcome="failure", result=detail)
            return FinalActionResult(self.action_id, self.action_type, "failed", "failure", detail)


def _safe_project_component(project_id: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", project_id).strip(".-")
    return value[:100] or "project"


class FallbackPatchFinalAction:
    """将远端动作失败恢复成可下载 Patch，但不满足原必需动作。"""

    action_id = "__fallback_patch__"
    action_type = "fallbackPatch"

    def __init__(
        self,
        *,
        store: DeliveryStore,
        data_root: Path,
        project_id: str,
        action_version: int = 1,
    ) -> None:
        self.store = store
        self.output_directory = (
            data_root.resolve() / "fallback-patches" / _safe_project_component(project_id)
        )
        self.action_version = action_version

    def execute(
        self,
        context: FrozenDeliveryContext,
        *,
        triggered_by: tuple[str, ...],
        reusable_patch: FinalActionResult | None,
    ) -> FinalActionResult:
        config = {
            "outputDirectory": str(self.output_directory),
            "filenameTemplate": "{task_id}-{run_id}-{change_version}.patch",
        }
        config_hash = hashlib.sha256(canonical_json(config).encode()).hexdigest()
        intent_key = hashlib.sha256(
            f"{context.run_id}:{self.action_id}:{self.action_version}:{config_hash}".encode()
        ).hexdigest()
        action = self.store.ensure_action(
            task_run_id=context.run_id,
            action_id=self.action_id,
            action_version=self.action_version,
            action_type=self.action_type,
            config_hash=config_hash,
            intent_key=intent_key,
        )
        action_db_id = int(action["id"])
        self.store.mark_action(action_db_id, status="running")
        try:
            if reusable_patch is not None:
                detail: dict[str, object] = {
                    "path": str(reusable_patch.detail["path"]),
                    "sha256": context.patch_sha256,
                    "adoptedExisting": True,
                    "reusedActionId": reusable_patch.action_id,
                    "triggeredBy": list(triggered_by),
                }
            else:
                delivered = deliver_patch(
                    patch_bytes=context.patch_path.read_bytes(),
                    expected_sha256=context.patch_sha256,
                    output_directory=self.output_directory,
                    filename=(
                        f"{context.task_id}-{context.run_id}-{context.change_version}.patch"
                    ),
                )
                detail = {
                    "path": str(delivered.path),
                    "sha256": delivered.sha256,
                    "adoptedExisting": delivered.adopted_existing,
                    "reusedActionId": None,
                    "triggeredBy": list(triggered_by),
                }
            self.store.mark_action(
                action_db_id, status="succeeded", outcome="success", result=detail
            )
            return FinalActionResult(
                self.action_id, self.action_type, "succeeded", "success", detail
            )
        except Exception as exc:
            detail = {
                "code": "fallback_patch_failed",
                "error": str(exc),
                "errorType": type(exc).__name__,
                "triggeredBy": list(triggered_by),
            }
            self.store.mark_action(
                action_db_id, status="failed", outcome="failure", result=detail
            )
            return FinalActionResult(
                self.action_id, self.action_type, "failed", "failure", detail
            )
