from __future__ import annotations

import os
import re
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import Any

from codefixer.adapters.agents import parse_agent_profile
from codefixer.application.services.workspace_detection import available_final_actions, detect_workspace, sanitize_remote_url
from codefixer.config import LoadedConfig

Check = dict[str, Any]


def _check(check_id: str, ok: bool, summary: str, suggestion: str | None = None, *, warning: bool = False) -> Check:
    status = "warning" if warning and ok else ("ready" if ok else "failed")
    value: Check = {"id": check_id, "status": status, "summary": summary}
    if suggestion:
        value["suggestion"] = suggestion
    return value


def _git_delivery_health(repository: Path, command: list[str]) -> tuple[bool, str]:
    try:
        process_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        layout = subprocess.run(
            [*command, "rev-parse", "--is-inside-work-tree"],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=process_env,
        )
        if layout.returncode != 0 or layout.stdout.strip() != "true":
            return False, "所选路径不是 Git 工作区"
        remote = subprocess.run(
            [*command, "remote", "get-url", "origin"],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
            env=process_env,
        )
        remote_url = remote.stdout.strip()
        if remote.returncode != 0 or not remote_url:
            return False, "仓库没有可用的 origin remote"
        probe = subprocess.run(
            [*command, "ls-remote", "--heads", "origin"],
            cwd=repository,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env=process_env,
        )
        if probe.returncode != 0:
            reason = probe.stderr.strip().splitlines()[-1] if probe.stderr.strip() else "远端访问失败"
            reason = re.sub(r"(https?://)[^/@\s]+@", r"\1***@", reason)
            return False, reason
        return True, f"Git remote 可访问：{sanitize_remote_url(remote_url)}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f"Git remote 检查失败：{exc}"


def _direct_path(raw: object) -> Path | None:
    value = str(raw or "").strip()
    if not value:
        return None
    path = Path(os.path.expandvars(os.path.expanduser(value)))
    return path.resolve(strict=False) if path.is_absolute() else None


def _writable_directory(path: Path | None) -> bool:
    if path is None:
        return False
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".codefixer-preflight"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def _workspace_policy_checks(workspace: dict[str, Any]) -> list[Check]:
    checks: list[Check] = []
    for key in ("allowedRoots", "deniedRoots"):
        values = workspace.get(key) or []
        valid = isinstance(values, list) and all(
            isinstance(value, str)
            and bool(value.strip())
            and not Path(value).is_absolute()
            and ".." not in Path(value).parts
            for value in values
        )
        checks.append(
            _check(
                f"workspace.policy.{key}",
                valid,
                f"{key}：{len(values) if isinstance(values, list) else 0} 项" if valid else f"{key} 必须是工作区内的相对路径列表",
                "移除绝对路径、空路径和 .. 路径段" if not valid else None,
            )
        )
    extensions = workspace.get("allowedExtensions") or []
    extensions_valid = isinstance(extensions, list) and all(
        isinstance(value, str) and value.startswith(".") and len(value) > 1 and "/" not in value and "\\" not in value
        for value in extensions
    )
    checks.append(
        _check(
            "workspace.policy.allowedExtensions",
            extensions_valid,
            f"允许扩展名：{len(extensions) if isinstance(extensions, list) else 0} 项" if extensions_valid else "allowedExtensions 格式无效",
            "扩展名应使用 .py、.ts 形式；空列表表示不按扩展名限制" if not extensions_valid else None,
        )
    )
    return checks


def normalize_project_configuration(project: dict[str, Any]) -> dict[str, Any]:
    """校验项目的物理来源与动作能力，并固化服务端重新探测的事实。"""

    normalized = deepcopy(project)
    localization = normalized.get("localizationSource")
    if not isinstance(localization, dict) or not str(localization.get("type", "")).strip():
        raise ValueError("必须配置带类型的定位源")
    localization_path = _direct_path(localization.get("path"))
    if localization_path is None or not localization_path.is_dir():
        raise ValueError("定位源必须是存在的绝对目录")
    localization["path"] = str(localization_path)

    workspace = normalized.get("modificationWorkspace")
    if not isinstance(workspace, dict):
        raise ValueError("必须配置修改工作区")
    workspace_path = _direct_path(workspace.get("path"))
    if workspace_path is None:
        raise ValueError("修改工作区必须使用绝对路径")
    detection = detect_workspace(str(workspace_path))
    if not detection.get("ready"):
        raise ValueError(str(detection.get("summary") or "修改工作区不可用"))
    for check in _workspace_policy_checks(workspace):
        if check["status"] == "failed":
            raise ValueError(str(check["summary"]))
    workspace["path"] = str(workspace_path)
    for key in ("vcsKind", "hostingKind", "repositoryRoot", "remoteUrl", "webBaseUrl"):
        if key in detection:
            workspace[key] = detection[key]
        else:
            workspace.pop(key, None)

    actions = normalized.get("finalActions")
    if not isinstance(actions, list) or not actions:
        raise ValueError("至少需要一个最终动作")
    action_ids = [str(action.get("id", "")).strip() for action in actions if isinstance(action, dict)]
    if len(action_ids) != len(actions) or any(not value for value in action_ids) or len(set(action_ids)) != len(action_ids):
        raise ValueError("最终动作 ID 不能为空或重复")
    allowed = available_final_actions(detection)
    delivery_log = normalized.get("deliveryLog")
    if not isinstance(delivery_log, dict):
        raise ValueError("必须配置交付日志")
    for key, label in (("technologyTag", "技术域"), ("branchLabel", "分支标签"), ("versionFallback", "版本或兜底版本"), ("submitterName", "提交人姓名")):
        if not str(delivery_log.get(key) or "").strip():
            raise ValueError(f"交付日志缺少{label}")
    for action in actions:
        action_type = str(action.get("type", ""))
        if action_type not in allowed:
            raise ValueError(f"{detection['vcsKind']}/{detection['hostingKind']} 修改工作区不支持 {action_type or '未配置动作'}")
        if action_type == "patch":
            output_directory = _direct_path(action.get("outputDirectory"))
            if output_directory is None:
                raise ValueError("Patch 输出目录必须使用绝对路径")
            action["outputDirectory"] = str(output_directory)
        if action_type == "githubPr":
            targets = action.get("targetBranches")
            if not isinstance(targets, list) or not targets or any(not isinstance(value, str) or not value.strip() for value in targets):
                raise ValueError(f"{action_type} 至少需要一个目标分支")
            if len(set(targets)) != len(targets):
                raise ValueError(f"{action_type} 的目标分支不能重复")
    return normalized


def run_project_preflight(loaded: LoadedConfig, project: dict[str, Any]) -> dict[str, Any]:
    checks: list[Check] = []
    project_id = str(project.get("id", "")).strip()
    checks.append(_check("project.id", bool(project_id), "项目 ID 已配置" if project_id else "缺少项目 ID"))
    localization = project.get("localizationSource") or {}
    localization_type = str(localization.get("type", "")).strip()
    localization_path = _direct_path(localization.get("path"))
    checks.append(_check("localization.type", bool(localization_type), f"定位源类型：{localization_type}" if localization_type else "缺少定位源类型"))
    localization_ok = localization_path is not None and localization_path.is_dir() and os.access(localization_path, os.R_OK)
    checks.append(
        _check(
            "localization.path",
            localization_ok,
            f"定位源可读取：{localization_path}" if localization_ok else "定位源路径无效或不可读取",
            "请选择当前服务进程可读取的绝对目录" if not localization_ok else None,
        )
    )

    workspace = project.get("modificationWorkspace") or {}
    workspace_path = _direct_path(workspace.get("path"))
    if workspace_path is None:
        detection = detect_workspace("")
        checks.append(_check("workspace.path", False, "缺少修改工作区路径", "请选择 Git 或 SVN 工作目录的绝对路径"))
    else:
        detection = detect_workspace(str(workspace_path))
        checks.extend(detection["checks"])
    checks.extend(_workspace_policy_checks(workspace))

    profiles = {str(item.get("id")): item for item in loaded.config.agentProfiles if item.get("id")}
    profile_id = loaded.config.execution.currentModelId.strip()
    raw_profile = profiles.get(profile_id)
    profile_ok = bool(profile_id and raw_profile is not None)
    checks.append(_check("agent.current", profile_ok, f"当前模型：{profile_id or '未配置'}", "在设置中选择当前模型" if not profile_ok else None))
    if profile_ok and raw_profile is not None:
        try:
            profile = parse_agent_profile(raw_profile)
        except (TypeError, ValueError) as exc:
            checks.append(_check("agent.current.profile", False, f"当前模型配置无效：{exc}", "重新选择当前模型或检查 Agent runtime 配置"))
        else:
            agent_binding = loaded.config.executableBindings.get(profile.executable_ref, {})
            agent_command = agent_binding.get("command") if isinstance(agent_binding, dict) else None
            agent_executable = str(agent_command[0]) if isinstance(agent_command, list) and agent_command else ""
            agent_executable_ok = bool(agent_executable and (Path(agent_executable).is_file() or shutil.which(agent_executable)))
            checks.append(_check("agent.current.executable", agent_executable_ok, f"{profile.runtime} CLI：{agent_executable or profile.executable_ref}", "检查当前模型对应 CLI 与当前机器 executableBindings/PATH" if not agent_executable_ok else None))

    verification = project.get("verification") or {}
    steps = verification.get("steps") or []
    allow_no_tests = bool(verification.get("allowNoAutomatedTests"))
    reason = str(verification.get("reason", "")).strip()
    verification_ok = bool(steps) or (allow_no_tests and bool(reason))
    checks.append(_check("verification.policy", verification_ok, f"已配置 {len(steps)} 个验证步骤" if steps else ("已显式声明无自动测试替代门禁" if verification_ok else "未配置验证策略"), "添加验证步骤，或显式填写 allowNoAutomatedTests 与 reason" if not verification_ok else None))
    actions = project.get("finalActions") or []
    checks.append(_check("delivery.actions", bool(actions), f"最终动作：{len(actions)} 个" if actions else "至少需要一个最终动作"))
    action_ids: set[str] = set()
    delivery_log = project.get("deliveryLog") if isinstance(project.get("deliveryLog"), dict) else {}
    log_ready = all(str(delivery_log.get(key) or "").strip() for key in ("technologyTag", "branchLabel", "versionFallback", "submitterName"))
    checks.append(_check("delivery.log", log_ready, "交付日志已配置" if log_ready else "交付日志缺少技术域、分支标签、版本或提交人", "在最终动作顶部补全交付日志" if not log_ready else None))
    for index, action in enumerate(actions):
        action_id = str(action.get("id", ""))
        action_type = str(action.get("type", ""))
        unique = bool(action_id and action_id not in action_ids)
        if action_id:
            action_ids.add(action_id)
        checks.append(_check(f"delivery.{index}.id", unique, f"动作 ID：{action_id or '未配置'}"))
        supported = action_type in {"patch", "gitlabPush", "githubPr"}
        checks.append(_check(f"delivery.{index}.type", supported, f"动作类型：{action_type or '未配置'}"))
        if supported:
            allowed = available_final_actions(detection)
            capability_ok = action_type in allowed
            checks.append(
                _check(
                    f"delivery.{index}.capability",
                    capability_ok,
                    f"{action_type} 与 {detection.get('vcsKind')}/{detection.get('hostingKind')} 工作区兼容" if capability_ok else f"当前工作区不支持 {action_type}",
                    "Patch 适用于全部有效工作区；GitLab Push/GitHub PR 只适用于对应托管类型" if not capability_ok else None,
                )
            )
        if action_type == "patch":
            output = _direct_path(action.get("outputDirectory"))
            output_ok = _writable_directory(output)
            checks.append(_check(f"delivery.{index}.patch_output", output_ok, f"Patch 输出：{output}" if output_ok else "Patch 输出目录无效或不可写", "请选择当前服务进程可写的绝对目录" if not output_ok else None))
        if action_type in {"gitlabPush", "githubPr"}:
            root_value = detection.get("repositoryRoot")
            repository = Path(str(root_value)) if root_value else None
            git_binding = loaded.config.executableBindings.get("git-cli", {})
            git_command = git_binding.get("command") if isinstance(git_binding, dict) else None
            if not isinstance(git_command, list) or not git_command:
                git_command = ["git"] if shutil.which("git") else None
            if repository is None or not repository.exists() or not isinstance(git_command, list) or not git_command:
                healthy, summary = False, "请选择存在的本地 Git 仓库"
            else:
                healthy, summary = _git_delivery_health(repository, [str(item) for item in git_command])
            checks.append(_check(f"delivery.{index}.remote", healthy, summary, "检查修改工作区、origin 与当前机器的 Git 认证" if not healthy else None))
            if action_type == "githubPr":
                targets = action.get("targetBranches") or []
                targets_ok = isinstance(targets, list) and bool(targets) and all(isinstance(value, str) and bool(value.strip()) for value in targets) and len(set(targets)) == len(targets)
                checks.append(_check(f"delivery.{index}.targets", targets_ok, f"目标分支：{len(targets)} 个" if targets_ok else "目标分支不能为空或重复"))

    if any(str(action.get("type")) in {"gitlabPush", "githubPr"} for action in actions):
        sanitized_project_id = re.sub(r"[^A-Za-z0-9._-]+", "-", project_id).strip(".-") or "project"
        fallback = loaded.data_root / "fallback-patches" / sanitized_project_id
        fallback_ok = _writable_directory(fallback)
        repository_root = Path(str(detection["repositoryRoot"])) if detection.get("repositoryRoot") else None
        if fallback_ok and repository_root is not None:
            try:
                fallback.resolve().relative_to(repository_root.resolve())
            except ValueError:
                pass
            else:
                fallback_ok = False
        checks.append(_check("delivery.fallback_patch", fallback_ok, f"保底 Patch 目录：{fallback}" if fallback_ok else "保底 Patch 目录不可用", "检查 storage.dataRoot 的可写性，且不要把数据目录放在修改仓库内" if not fallback_ok else None))
    failed = [item for item in checks if item["status"] == "failed"]
    return {"projectId": project_id, "ready": not failed, "status": "ready" if not failed else "not_ready", "checks": checks}
