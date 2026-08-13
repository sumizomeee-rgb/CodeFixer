from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from codefixer.config import LoadedConfig


def _referenced_executables(loaded: LoadedConfig) -> set[str]:
    profiles = {
        str(item.get("id")): item
        for item in loaded.config.agentProfiles
        if item.get("id")
    }
    references: set[str] = set()
    current_profile = profiles.get(loaded.config.execution.currentModelId)
    if current_profile and current_profile.get("executableRef"):
        references.add(str(current_profile["executableRef"]))
    for project in loaded.config.projects:
        if project.get("enabled", True) is False:
            continue
        source = project.get("modificationSource") or {}
        if source.get("executableRef"):
            references.add(str(source["executableRef"]))
        for step in (project.get("verification") or {}).get("steps") or []:
            if step.get("executableRef"):
                references.add(str(step["executableRef"]))
        for action in project.get("finalActions") or []:
            if action.get("type") == "gitlabMr":
                references.add(str(action.get("gitExecutableRef") or "git-cli"))
    return references


def _extract_version(output: str, pattern: str | None) -> str | None:
    matcher = re.search(pattern or r"(?<!\d)(\d+(?:\.\d+){1,3})(?!\d)", output)
    if matcher is None:
        return None
    return matcher.group(1) if matcher.lastindex else matcher.group(0)


def _version_tuple(value: str) -> tuple[int, ...]:
    return tuple(int(part) for part in value.split("."))


def _constraint_satisfied(version: str, constraint: str) -> bool:
    match = re.fullmatch(r"\s*(>=|<=|==|>|<)?\s*(\d+(?:\.\d+){1,3})\s*", constraint)
    if match is None:
        return False
    operator = match.group(1) or ">="
    actual = _version_tuple(version)
    expected = _version_tuple(match.group(2))
    width = max(len(actual), len(expected))
    actual += (0,) * (width - len(actual))
    expected += (0,) * (width - len(expected))
    return {
        ">=": actual >= expected,
        "<=": actual <= expected,
        "==": actual == expected,
        ">": actual > expected,
        "<": actual < expected,
    }[operator]


def inspect_executable_dependencies(loaded: LoadedConfig) -> list[dict[str, Any]]:
    required = _referenced_executables(loaded)
    checks: list[dict[str, Any]] = []
    for binding_id, binding in loaded.config.executableBindings.items():
        command = binding.get("command") if isinstance(binding, dict) else None
        executable = str(command[0]) if isinstance(command, list) and command else ""
        is_required = binding_id in required
        resolved = str(Path(executable).resolve()) if executable and Path(executable).is_file() else shutil.which(executable)
        base: dict[str, Any] = {
            "id": f"dependency.{binding_id}",
            "dependencyId": binding_id,
            "required": is_required,
            "command": executable,
        }
        if not resolved:
            base.update(
                status="failed" if is_required else "inactive",
                summary=f"{binding_id} 未找到" if is_required else f"{binding_id} 尚未安装（当前未使用）",
                suggestion=f"安装 {executable or binding_id}，或修正 executableBindings.{binding_id}",
            )
            checks.append(base)
            continue
        version_args = binding.get("versionArgs") or ["--version"]
        try:
            result = subprocess.run(
                [resolved, *[str(item) for item in version_args]],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            base.update(
                status="failed" if is_required else "inactive",
                summary=f"{binding_id} 版本检查失败",
                detail=str(exc),
                suggestion="确认部署用户可以非交互执行该命令",
            )
            checks.append(base)
            continue
        output = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part.strip())
        version = _extract_version(output, binding.get("versionRegex"))
        constraint = binding.get("versionConstraint")
        base.update(path=resolved, version=version, detail=output[:500])
        if result.returncode != 0 or version is None:
            base.update(
                status="failed" if is_required else "inactive",
                summary=f"{binding_id} 无法确认版本",
                suggestion="检查 versionArgs/versionRegex，并确认命令可正常执行",
            )
        elif constraint and not _constraint_satisfied(version, str(constraint)):
            base.update(
                status="failed" if is_required else "warning",
                summary=f"{binding_id} {version} 不满足 {constraint}",
                suggestion=f"升级该工具或调整 executableBindings.{binding_id}.versionConstraint",
            )
        elif not constraint:
            base.update(
                status="ready",
                summary=f"{binding_id} {version} 可用",
                suggestion=f"为 executableBindings.{binding_id} 配置 versionConstraint",
            )
        else:
            base.update(status="ready", summary=f"{binding_id} {version} 可用")
        checks.append(base)
    return checks
