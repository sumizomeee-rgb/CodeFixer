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


def _git_delivery_health(remote_url: str, command: list[str], *, cwd: Path) -> tuple[bool, str]:
    try:
        process_env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        probe = subprocess.run(
            [*command, "ls-remote", "--heads", remote_url],
            cwd=cwd,
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
        return True, f"权威 Git 远端可访问：{sanitize_remote_url(remote_url)}"
    except (OSError, subprocess.TimeoutExpired):
        return False, "Git remote 检查无法执行或超时"


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
    for rule in normalized.get("routingRules") or []:
        if not isinstance(rule, dict):
            raise ValueError("工单接收规则格式无效")
        version_filter = rule.get("versionFilter")
        if version_filter is None:
            continue
        if not isinstance(version_filter, dict):
            raise ValueError("接收版本配置格式无效")
        mode = str(version_filter.get("mode", "all"))
        if mode not in {"all", "selected"}:
            raise ValueError("接收版本只能是全部版本或指定版本")
        versions = version_filter.get("versions") or []
        if not isinstance(versions, list):
            raise ValueError("指定版本必须是版本列表")
        normalized_versions: list[dict[str, str]] = []
        seen: set[str] = set()
        for version in versions:
            if not isinstance(version, dict):
                raise ValueError("指定版本格式无效")
            version_id = str(version.get("id") or "").strip()
            name = str(version.get("name") or "").strip()
            if not version_id or not name:
                raise ValueError("指定版本缺少内部标识或名称")
            if version_id in seen:
                raise ValueError("指定版本不能重复")
            seen.add(version_id)
            normalized_versions.append({"id": version_id, "name": name})
        if mode == "selected" and not normalized_versions:
            raise ValueError("选择指定版本后，至少需要选择一个版本")
        rule["versionFilter"] = {
            "mode": mode,
            "versions": normalized_versions if mode == "selected" else [],
        }

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
    location_type = str(workspace.get("locationType") or "").strip()
    if location_type == "local":
        local_path = _direct_path(workspace.get("localPath"))
        if local_path is None:
            raise ValueError("本地修改源必须使用绝对路径")
        detection = detect_workspace(str(local_path), location_type="local")
    elif location_type == "remote":
        remote_url = str(workspace.get("remoteUrl") or "").strip()
        if not remote_url:
            raise ValueError("远端修改源必须填写仓库 URL")
        detection = detect_workspace(remote_url, location_type="remote")
    else:
        raise ValueError("修改源入口类型必须是本地仓库或远端 URL")
    if not detection.get("ready"):
        failure = next((item for item in detection.get("checks") or [] if item.get("status") == "failed"), None)
        raise ValueError(str((failure or {}).get("summary") or detection.get("summary") or "修改源不可用"))
    for check in _workspace_policy_checks(workspace):
        if check["status"] == "failed":
            raise ValueError(str(check["summary"]))
    workspace["locationType"] = location_type
    if location_type == "local":
        workspace["localPath"] = str(detection["location"])
    else:
        workspace.pop("localPath", None)
    workspace.pop("path", None)
    workspace.pop("repositoryRoot", None)
    for key in ("vcsKind", "hostingKind", "remoteUrl", "webBaseUrl"):
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
    delivery_log.pop("branchLabel", None)
    delivery_log.pop("versionSource", None)
    delivery_log.pop("versionFallback", None)
    for key, label in (("technologyTag", "技术域"), ("submitterName", "提交人姓名")):
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
    checks.append(_check("project.id", bool(project_id), "流水线内部标识已生成" if project_id else "缺少流水线内部标识"))
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
    location_type = str(workspace.get("locationType") or "")
    remote_url = str(workspace.get("remoteUrl") or "").strip()
    if location_type not in {"local", "remote"}:
        checks.append(_check("workspace.location_type", False, "缺少修改源入口类型", "请选择本地仓库或远端 URL"))
    detection = detect_workspace(remote_url, location_type="remote")
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
    log_ready = all(str(delivery_log.get(key) or "").strip() for key in ("technologyTag", "submitterName"))
    checks.append(_check("delivery.log", log_ready, "交付日志已配置" if log_ready else "交付日志缺少技术域或提交人", "在最终动作顶部补全交付日志" if not log_ready else None))
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
            remote_url = str(detection.get("remoteUrl") or "").strip()
            git_binding = loaded.config.executableBindings.get("git-cli", {})
            git_command = git_binding.get("command") if isinstance(git_binding, dict) else None
            if not isinstance(git_command, list) or not git_command:
                git_command = ["git"] if shutil.which("git") else None
            loaded.data_root.mkdir(parents=True, exist_ok=True)
            if not remote_url or not isinstance(git_command, list) or not git_command:
                healthy, summary = False, "缺少可访问的权威 Git 远端"
            else:
                healthy, summary = _git_delivery_health(remote_url, [str(item) for item in git_command], cwd=loaded.data_root)
            checks.append(_check(f"delivery.{index}.remote", healthy, summary, "检查修改工作区、origin 与当前机器的 Git 认证" if not healthy else None))
            if action_type == "githubPr":
                targets = action.get("targetBranches") or []
                targets_ok = isinstance(targets, list) and bool(targets) and all(isinstance(value, str) and bool(value.strip()) for value in targets) and len(set(targets)) == len(targets)
                checks.append(_check(f"delivery.{index}.targets", targets_ok, f"目标分支：{len(targets)} 个" if targets_ok else "目标分支不能为空或重复"))

    if any(str(action.get("type")) in {"gitlabPush", "githubPr"} for action in actions):
        sanitized_project_id = re.sub(r"[^A-Za-z0-9._-]+", "-", project_id).strip(".-") or "project"
        fallback = loaded.data_root / "fallback-patches" / sanitized_project_id
        fallback_ok = _writable_directory(fallback)
        checks.append(_check("delivery.fallback_patch", fallback_ok, f"保底 Patch 目录：{fallback}" if fallback_ok else "保底 Patch 目录不可用", "检查 storage.dataRoot 的可写性，且不要把数据目录放在修改仓库内" if not fallback_ok else None))
    failed = [item for item in checks if item["status"] == "failed"]
    return {"projectId": project_id, "ready": not failed, "status": "ready" if not failed else "not_ready", "checks": checks}
