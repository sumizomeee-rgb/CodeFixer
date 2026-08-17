from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


@dataclass(frozen=True)
class LocalizationApplyResult:
    target: Path
    copied: int
    deleted: int


def _json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取冻结任务数据：{path.name}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"冻结任务数据格式无效：{path.name}")
    return value


def _relative_path(value: object) -> PurePosixPath:
    path = PurePosixPath(str(value or "").replace("\\", "/"))
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"冻结文件路径越界：{value}")
    return path


def _within(root: Path, relative: PurePosixPath) -> Path:
    target = (root / Path(*relative.parts)).resolve()
    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"冻结文件路径越过定位目录：{relative}") from exc
    return target


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".codefixer", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def apply_frozen_change_to_localization(
    *,
    task: dict[str, Any],
    data_root: Path,
    current_project: dict[str, Any],
) -> LocalizationApplyResult:
    if task.get("status") != "completed" or task.get("result") != "changed":
        raise ValueError("仅已完成且包含代码修改的任务可以同步到定位资料")
    task_id = str(task.get("id") or "")
    run_id = str(task.get("current_run_id") or "")
    project_id = str(task.get("project_id") or "")
    if not task_id or not run_id or not project_id or str(current_project.get("id") or "") != project_id:
        raise ValueError("任务所属流水线已不存在")
    root = data_root.resolve()
    run_root = (root / "tasks" / task_id / "runs" / run_id).resolve()
    try:
        run_root.relative_to(root)
    except ValueError as exc:
        raise ValueError("任务运行目录越界") from exc
    manifest = _json_object(run_root / "freeze-change" / "change-manifest.json")
    config_snapshot = _json_object(run_root / "snapshot" / "config-snapshot.json")
    frozen_project = config_snapshot.get("project")
    if not isinstance(frozen_project, dict):
        raise ValueError("任务缺少冻结流水线配置")
    frozen_localization = frozen_project.get("localizationSource")
    current_localization = current_project.get("localizationSource")
    if not isinstance(frozen_localization, dict) or not isinstance(current_localization, dict):
        raise ValueError("流水线缺少定位资料配置")
    frozen_path_value = str(frozen_localization.get("path") or "").strip()
    current_path_value = str(current_localization.get("path") or "").strip()
    if not frozen_path_value or not current_path_value:
        raise ValueError("流水线缺少定位资料目录")
    frozen_path = Path(frozen_path_value).resolve()
    current_path = Path(current_path_value).resolve()
    if frozen_path != current_path or str(frozen_localization.get("id") or "") != str(current_localization.get("id") or ""):
        raise ValueError("流水线的定位资料已变更，请勿把旧任务写入新的定位目录")
    if not current_path.is_dir():
        raise ValueError("定位资料目录不存在")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("任务没有可同步的冻结文件")
    planned: list[tuple[str, Path, bytes | None]] = []
    frozen_files = (run_root / "freeze-change" / "files").resolve()
    rename_sources: dict[str, PurePosixPath] = {}
    try:
        rename_from: PurePosixPath | None = None
        for line in (run_root / "freeze-change" / "change.patch").read_text(encoding="utf-8").splitlines():
            if line.startswith("rename from "):
                rename_from = _relative_path(line.removeprefix("rename from "))
            elif line.startswith("rename to ") and rename_from is not None:
                rename_to = _relative_path(line.removeprefix("rename to "))
                rename_sources[rename_to.as_posix()] = rename_from
                rename_from = None
    except (OSError, UnicodeError):
        pass
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("冻结文件清单格式无效")
        relative = _relative_path(item.get("path"))
        operation = str(item.get("operation") or "modify")
        if operation not in {"add", "modify", "delete", "rename"}:
            raise ValueError(f"冻结文件操作无效：{operation}")
        target = _within(current_path, relative)
        if operation == "delete":
            planned.append((operation, target, None))
            continue
        source = _within(frozen_files, relative)
        if not source.is_file():
            raise ValueError(f"冻结文件不存在：{relative}")
        content = source.read_bytes()
        expected = str(item.get("content_sha256") or "")
        if not expected or hashlib.sha256(content).hexdigest() != expected:
            raise ValueError(f"冻结文件校验失败：{relative}")
        planned.append((operation, target, content))
    copied = 0
    deleted = 0
    for operation, target, content in planned:
        if operation == "delete":
            if target.is_dir() and not target.is_symlink():
                raise ValueError(f"拒绝删除目录：{target}")
            if target.exists() or target.is_symlink():
                target.unlink()
                deleted += 1
            continue
        assert content is not None
        _write_atomic(target, content)
        copied += 1
        if operation == "rename":
            old_relative = rename_sources.get(
                target.relative_to(current_path).as_posix()
            )
            if old_relative is not None:
                old_target = _within(current_path, old_relative)
                if old_target != target and (old_target.exists() or old_target.is_symlink()):
                    if old_target.is_dir() and not old_target.is_symlink():
                        raise ValueError(f"拒绝删除目录：{old_target}")
                    old_target.unlink()
                    deleted += 1
    return LocalizationApplyResult(current_path, copied, deleted)
