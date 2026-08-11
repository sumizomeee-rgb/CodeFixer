from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from codefixer.config import LoadedConfig

Check = dict[str, Any]


def _check(check_id: str, ok: bool, summary: str, suggestion: str | None = None) -> Check:
    value: Check = {"id": check_id, "status": "ready" if ok else "failed", "summary": summary}
    if suggestion:
        value["suggestion"] = suggestion
    return value


def resolve_path_binding(loaded: LoadedConfig, binding_id: str) -> Path | None:
    raw = loaded.config.pathBindings.get(binding_id)
    if raw is None:
        return None
    path = Path(raw)
    return path.resolve() if path.is_absolute() else (loaded.data_root / path).resolve()


def run_project_preflight(loaded: LoadedConfig, project: dict[str, Any]) -> dict[str, Any]:
    checks: list[Check] = []
    project_id = str(project.get("id", "")).strip()
    checks.append(_check("project.id", bool(project_id), "项目 ID 已配置" if project_id else "缺少项目 ID"))
    source = project.get("modificationSource") or {}
    source_type = str(source.get("type", ""))
    checks.append(_check("source.type", source_type in {"git", "svn"}, f"修改源类型：{source_type or '未配置'}"))
    repository_ref = str(source.get("repositoryRef", ""))
    repository_path = resolve_path_binding(loaded, repository_ref) if repository_ref else None
    repo_ok = repository_path is not None and repository_path.exists()
    checks.append(_check("source.repository", repo_ok, f"仓库路径：{repository_path}" if repository_path else "修改源 repositoryRef 无法解析", "在 pathBindings 中配置当前机器的仓库/工作副本路径" if not repo_ok else None))
    if repository_path is not None and repository_path.exists() and source_type == "git":
        checks.append(_check("source.git_layout", (repository_path / ".git").exists(), "Git 工作区可识别", "repositoryRef 必须指向 Git working tree"))
    if repository_path is not None and repository_path.exists() and source_type == "svn":
        checks.append(_check("source.svn_layout", (repository_path / ".svn").exists(), "SVN 工作副本可识别", "repositoryRef 必须指向 SVN working copy"))
    executable_ref = str(source.get("executableRef", ""))
    binding = loaded.config.executableBindings.get(executable_ref, {}) if executable_ref else {}
    command = binding.get("command") if isinstance(binding, dict) else None
    executable = str(command[0]) if isinstance(command, list) and command else ""
    executable_ok = bool(executable and (Path(executable).is_file() or shutil.which(executable)))
    checks.append(_check("source.executable", executable_ok, f"CLI 可用：{executable}" if executable_ok else f"CLI 不可用：{executable_ref or '未配置'}", "检查 executableBindings 与部署用户 PATH" if not executable_ok else None))
    profiles = {str(item.get("id")): item for item in loaded.config.agentProfiles if item.get("id")}
    agents = project.get("agents") or {}
    for role in ("discovery", "repair", "review"):
        profile_id = str(agents.get(role, ""))
        checks.append(_check(f"agent.{role}", bool(profile_id and profile_id in profiles), f"{role} profile：{profile_id or '未配置'}", "配置并引用有效 Agent profile" if not profile_id or profile_id not in profiles else None))
    verification = project.get("verification") or {}
    steps = verification.get("steps") or []
    allow_no_tests = bool(verification.get("allowNoAutomatedTests"))
    reason = str(verification.get("reason", "")).strip()
    verification_ok = bool(steps) or (allow_no_tests and bool(reason))
    checks.append(_check("verification.policy", verification_ok, f"已配置 {len(steps)} 个验证步骤" if steps else ("已显式声明无自动测试替代门禁" if verification_ok else "未配置验证策略"), "添加验证步骤，或显式填写 allowNoAutomatedTests 与 reason" if not verification_ok else None))
    actions = project.get("finalActions") or []
    checks.append(_check("delivery.actions", bool(actions), f"最终动作：{len(actions)} 个" if actions else "至少需要一个最终动作"))
    action_ids: set[str] = set()
    for index, action in enumerate(actions):
        action_id = str(action.get("id", ""))
        action_type = str(action.get("type", ""))
        unique = bool(action_id and action_id not in action_ids)
        if action_id:
            action_ids.add(action_id)
        checks.append(_check(f"delivery.{index}.id", unique, f"动作 ID：{action_id or '未配置'}"))
        checks.append(_check(f"delivery.{index}.type", action_type in {"patch", "gitlabMr"}, f"动作类型：{action_type or '未配置'}"))
        if action_type == "patch":
            output_ref = str(action.get("outputDirectoryRef", ""))
            output = resolve_path_binding(loaded, output_ref) if output_ref else None
            output_ok = output is not None
            if output is not None:
                try:
                    output.mkdir(parents=True, exist_ok=True)
                    probe = output / ".codefixer-preflight"
                    probe.write_text("ok", encoding="utf-8")
                    probe.unlink(missing_ok=True)
                except OSError:
                    output_ok = False
            checks.append(_check(f"delivery.{index}.patch_output", output_ok, f"Patch 输出：{output}" if output else "Patch outputDirectoryRef 无法解析"))
        if action_type == "gitlabMr":
            connection_ref = str(action.get("connectionRef", ""))
            connections = {str(item.get("id")) for item in loaded.config.connections if item.get("id")}
            checks.append(_check(f"delivery.{index}.gitlab_connection", connection_ref in connections, f"GitLab connection：{connection_ref or '未配置'}"))
            targets = action.get("targetBranches") or []
            checks.append(_check(f"delivery.{index}.targets", bool(targets), f"目标分支：{len(targets)} 个" if targets else "未配置目标分支"))
    failed = [item for item in checks if item["status"] == "failed"]
    return {"projectId": project_id, "ready": not failed, "status": "ready" if not failed else "not_ready", "checks": checks}
