from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


WorkspaceCheck = dict[str, str]
WorkspaceDetection = dict[str, Any]


def _check(check_id: str, status: str, summary: str, detail: str | None = None) -> WorkspaceCheck:
    value = {"id": check_id, "status": status, "summary": summary}
    if detail:
        value["detail"] = detail
    return value


def _run(command: list[str], *, cwd: Path, timeout: int = 10) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _command_detail(result: subprocess.CompletedProcess[str] | None) -> str | None:
    if result is None:
        return "命令不可用或执行超时"
    output = (result.stderr or result.stdout).strip()
    if not output:
        return f"命令退出码：{result.returncode}"
    # 诊断只返回末尾一行，避免把凭据或大量命令输出带入配置页面。
    return output.splitlines()[-1][:500]


def _remote_host(remote_url: str) -> str:
    raw = remote_url.strip()
    if not raw:
        return ""
    if "://" in raw:
        return (urlparse(raw).hostname or "").lower().rstrip(".")
    match = re.match(r"^(?:[^@/\s]+@)?([^:/\s]+):.+$", raw)
    return match.group(1).lower().rstrip(".") if match else ""


def sanitize_remote_url(remote_url: str) -> str:
    """保留仓库定位信息，但绝不把 URL 内嵌凭据返回给 Web。"""

    raw = remote_url.strip()
    if "://" not in raw:
        return raw
    parsed = urlparse(raw)
    host = parsed.hostname or ""
    if parsed.port:
        host = f"{host}:{parsed.port}"
    if parsed.scheme == "ssh" and parsed.username and parsed.password is None:
        host = f"{parsed.username}@{host}"
    return parsed._replace(netloc=host, query="", fragment="").geturl()


def _hosting_kind(remote_urls: list[str]) -> str:
    hosts = {_remote_host(value) for value in remote_urls}
    hosts.discard("")
    kinds: set[str] = set()
    if "gitlab.com" in hosts:
        kinds.add("gitlab")
    if "github.com" in hosts:
        kinds.add("github")
    if len(kinds) > 1:
        return "ambiguous"
    if kinds:
        return kinds.pop()
    return "other"


def _base_result(path: Path) -> WorkspaceDetection:
    return {
        "path": str(path),
        "ready": False,
        "vcsKind": "unknown",
        "hostingKind": "none",
        "summary": "无法识别修改工作区",
        "checks": [],
    }


def detect_workspace(raw_path: str) -> WorkspaceDetection:
    """确定性探测本机目录的版本控制类型与可用交付能力。"""

    expanded = os.path.expandvars(os.path.expanduser(raw_path.strip()))
    path = Path(expanded).resolve(strict=False) if expanded else Path("").resolve()
    detection = _base_result(path)
    checks: list[WorkspaceCheck] = detection["checks"]
    if not raw_path.strip():
        detection["path"] = ""
        checks.append(_check("workspace.path", "failed", "请选择修改工作区目录"))
        return detection
    if not path.exists():
        checks.append(_check("workspace.path", "failed", "目录不存在", str(path)))
        return detection
    if not path.is_dir():
        checks.append(_check("workspace.path", "failed", "所选路径不是目录", str(path)))
        return detection
    checks.append(_check("workspace.path", "ready", "目录存在", str(path)))

    writable = os.access(path, os.R_OK | os.W_OK)
    checks.append(
        _check(
            "workspace.access",
            "ready" if writable else "failed",
            "目录可读写" if writable else "目录不可读写",
            None if writable else "修改工作区必须允许当前服务进程读取和写入",
        )
    )

    inside_git = _run(["git", "rev-parse", "--is-inside-work-tree"], cwd=path)
    if inside_git is not None and inside_git.returncode == 0 and inside_git.stdout.strip() == "true":
        root_result = _run(["git", "rev-parse", "--show-toplevel"], cwd=path)
        root_text = root_result.stdout.strip() if root_result is not None and root_result.returncode == 0 else ""
        if not root_text:
            checks.append(_check("workspace.git.root", "failed", "无法读取 Git 仓库根目录", _command_detail(root_result)))
            return detection
        repository_root = Path(root_text).resolve(strict=False)
        remote_result = _run(["git", "remote", "get-url", "--all", "origin"], cwd=repository_root)
        remote_urls = (
            [line.strip() for line in remote_result.stdout.splitlines() if line.strip()]
            if remote_result is not None and remote_result.returncode == 0
            else []
        )
        hosting_kind = _hosting_kind(remote_urls)
        detection.update(
            {
                "ready": writable,
                "vcsKind": "git",
                "hostingKind": hosting_kind,
                "repositoryRoot": str(repository_root),
                "summary": {
                    "gitlab": "已识别为 GitLab Git 工作区",
                    "github": "已识别为 GitHub Git 工作区",
                    "ambiguous": "Git origin 指向多个托管平台，仅可使用 Patch",
                    "other": "已识别为 Git 工作区，仅可使用 Patch",
                }[hosting_kind],
            }
        )
        safe_remote_urls = [sanitize_remote_url(value) for value in remote_urls]
        if safe_remote_urls:
            detection["remoteUrl"] = safe_remote_urls[0]
        checks.append(_check("workspace.vcs", "ready", "Git 工作区可识别", str(repository_root)))
        if not remote_urls:
            checks.append(_check("workspace.remote", "warning", "未配置 origin，仅可使用 Patch", _command_detail(remote_result)))
        elif hosting_kind == "ambiguous":
            checks.append(_check("workspace.hosting", "warning", "origin 托管类型存在歧义，仅可使用 Patch", "；".join(safe_remote_urls)))
        elif hosting_kind == "other":
            checks.append(_check("workspace.hosting", "warning", "未识别为 GitLab 或 GitHub，仅可使用 Patch", safe_remote_urls[0]))
        else:
            checks.append(_check("workspace.hosting", "ready", f"已识别 {hosting_kind}", safe_remote_urls[0]))
        return detection

    svn_root_result = _run(["svn", "info", "--show-item", "wc-root"], cwd=path)
    svn_root_text = svn_root_result.stdout.strip() if svn_root_result is not None and svn_root_result.returncode == 0 else ""
    if svn_root_text:
        repository_root = Path(svn_root_text).resolve(strict=False)
        detection.update(
            {
                "ready": writable,
                "vcsKind": "svn",
                "hostingKind": "none",
                "repositoryRoot": str(repository_root),
                "summary": "已识别为 SVN 工作副本",
            }
        )
        checks.append(_check("workspace.vcs", "ready", "SVN 工作副本可识别", str(repository_root)))
        return detection

    details = [value for value in (_command_detail(inside_git), _command_detail(svn_root_result)) if value]
    checks.append(_check("workspace.vcs", "failed", "不是有效的 Git 或 SVN 工作目录", "；".join(details)))
    return detection


def available_final_actions(detection: WorkspaceDetection) -> set[str]:
    if not detection.get("ready"):
        return set()
    actions = {"patch"}
    if detection.get("vcsKind") == "git" and detection.get("hostingKind") == "gitlab":
        actions.add("gitlabMr")
    if detection.get("vcsKind") == "git" and detection.get("hostingKind") == "github":
        actions.add("githubPr")
    return actions
