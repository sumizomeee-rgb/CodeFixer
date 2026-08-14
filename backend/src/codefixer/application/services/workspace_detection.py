from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx


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


def _safe_command_detail(
    result: subprocess.CompletedProcess[str] | None,
    remote_urls: list[str],
) -> str | None:
    detail = _command_detail(result)
    if detail is None:
        return None
    for remote_url in remote_urls:
        detail = detail.replace(remote_url, sanitize_remote_url(remote_url))
    return re.sub(r"(?i)\b([a-z][a-z0-9+.-]*://)[^/@\s]+@", r"\1", detail)


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


def _probe_gitlab_web_base(host: str) -> str | None:
    if not host:
        return None
    if host == "gitlab.com":
        return "https://gitlab.com"
    for scheme in ("https", "http"):
        base = f"{scheme}://{host}"
        for path in ("/-/health", "/users/sign_in"):
            try:
                response = httpx.get(
                    f"{base}{path}",
                    timeout=2.5,
                    follow_redirects=True,
                    verify=False,
                    headers={"User-Agent": "CodeFixer/1.0"},
                )
            except httpx.HTTPError:
                continue
            body = response.text.lower()
            is_gitlab = response.status_code == 200 and (
                'property="og:site_name"' in body and 'content="gitlab"' in body
                or "<title>" in body and "gitlab</title>" in body
                or path == "/-/health" and "gitlab" in body
            )
            if is_gitlab:
                final = response.url.copy_with(path="", query=None, fragment=None)
                return str(final).rstrip("/")
    return None


def _base_result(*, location: str, location_type: Literal["local", "remote"]) -> WorkspaceDetection:
    return {
        "location": location,
        "locationType": location_type,
        "ready": False,
        "vcsKind": "unknown",
        "hostingKind": "none",
        "summary": "无法识别修改工作区",
        "checks": [],
    }


def _git_detection(
    detection: WorkspaceDetection,
    *,
    remote_urls: list[str],
    repository_root: Path | None,
    ready: bool,
    remote_only: bool,
) -> WorkspaceDetection:
    checks: list[WorkspaceCheck] = detection["checks"]
    hosting_kind = _hosting_kind(remote_urls)
    web_base_url: str | None = None
    hosts = {_remote_host(value) for value in remote_urls if _remote_host(value)}
    if hosting_kind == "gitlab":
        web_base_url = "https://gitlab.com"
    elif hosting_kind == "github":
        web_base_url = "https://github.com"
    elif hosting_kind == "other" and len(hosts) == 1:
        web_base_url = _probe_gitlab_web_base(next(iter(hosts)))
        if web_base_url:
            hosting_kind = "gitlab"
    summary_suffix = "远端仓库" if remote_only else "工作区"
    detection.update(
        {
            "ready": ready,
            "vcsKind": "git",
            "hostingKind": hosting_kind,
            "summary": {
                "gitlab": f"已识别为 GitLab Git {summary_suffix}",
                "github": f"已识别为 GitHub Git {summary_suffix}",
                "ambiguous": "Git origin 指向多个托管平台，仅可使用 Patch",
                "other": f"已识别为 Git {summary_suffix}，仅可使用 Patch",
            }[hosting_kind],
        }
    )
    if repository_root is not None:
        detection["repositoryRoot"] = str(repository_root)
    safe_remote_urls = [sanitize_remote_url(value) for value in remote_urls]
    if len(safe_remote_urls) == 1:
        detection["remoteUrl"] = safe_remote_urls[0]
    if web_base_url:
        detection["webBaseUrl"] = web_base_url
    checks.append(
        _check(
            "workspace.vcs",
            "ready",
            "Git 远端仓库可识别" if remote_only else "Git 工作区可识别",
            safe_remote_urls[0] if remote_only and safe_remote_urls else str(repository_root),
        )
    )
    if hosting_kind == "ambiguous":
        checks.append(_check("workspace.hosting", "warning", "origin 托管类型存在歧义", "；".join(safe_remote_urls)))
    elif hosting_kind == "other" and safe_remote_urls:
        checks.append(_check("workspace.hosting", "warning", "未识别为 GitLab 或 GitHub，仅可使用 Patch", safe_remote_urls[0]))
    elif safe_remote_urls:
        checks.append(_check("workspace.hosting", "ready", f"已识别 {hosting_kind}", safe_remote_urls[0]))
    return detection


def _detect_remote(raw_location: str) -> WorkspaceDetection:
    remote_url = raw_location.strip()
    safe_remote_url = sanitize_remote_url(remote_url)
    detection = _base_result(location=safe_remote_url, location_type="remote")
    checks: list[WorkspaceCheck] = detection["checks"]
    if not remote_url:
        checks.append(_check("workspace.location", "failed", "请输入远端仓库地址"))
        return detection

    command_cwd = Path.cwd()
    git_result = _run(["git", "ls-remote", "--symref", remote_url, "HEAD"], cwd=command_cwd)
    if git_result is not None and git_result.returncode == 0 and git_result.stdout.strip():
        checks.append(_check("workspace.remote", "ready", "Git 远端连接成功", safe_remote_url))
        return _git_detection(
            detection,
            remote_urls=[remote_url],
            repository_root=None,
            ready=True,
            remote_only=True,
        )

    svn_result = _run(
        ["svn", "info", "--non-interactive", "--show-item", "revision", "--revision", "HEAD", remote_url],
        cwd=command_cwd,
    )
    if svn_result is not None and svn_result.returncode == 0 and svn_result.stdout.strip():
        detection.update(
            {
                "ready": True,
                "vcsKind": "svn",
                "hostingKind": "none",
                "remoteUrl": safe_remote_url,
                "summary": "已识别为 SVN 远端仓库",
            }
        )
        checks.extend(
            [
                _check("workspace.remote", "ready", "SVN 远端连接成功", safe_remote_url),
                _check("workspace.vcs", "ready", "SVN 远端仓库可识别", safe_remote_url),
            ]
        )
        return detection

    details = [
        value
        for value in (
            _safe_command_detail(git_result, [remote_url]),
            _safe_command_detail(svn_result, [remote_url]),
        )
        if value
    ]
    checks.append(_check("workspace.remote", "failed", "无法连接 Git 或 SVN 远端仓库", "；".join(details)))
    return detection


def detect_workspace(
    location: str,
    location_type: Literal["local", "remote"] = "local",
) -> WorkspaceDetection:
    """探测本机仓库入口或真实远端仓库地址。"""

    if location_type == "remote":
        return _detect_remote(location)
    if location_type != "local":
        raise ValueError(f"unsupported workspace location type: {location_type}")

    raw_path = location
    expanded = os.path.expandvars(os.path.expanduser(raw_path.strip()))
    path = Path(expanded).resolve(strict=False) if expanded else Path("").resolve()
    detection = _base_result(location=str(path) if raw_path.strip() else "", location_type="local")
    checks: list[WorkspaceCheck] = detection["checks"]
    if not raw_path.strip():
        checks.append(_check("workspace.path", "failed", "请选择修改工作区目录"))
        return detection
    if not path.exists():
        checks.append(_check("workspace.path", "failed", "目录不存在", str(path)))
        return detection
    if not path.is_dir():
        checks.append(_check("workspace.path", "failed", "所选路径不是目录", str(path)))
        return detection
    checks.append(_check("workspace.path", "ready", "目录存在", str(path)))

    readable = os.access(path, os.R_OK)
    checks.append(
        _check(
            "workspace.access",
            "ready" if readable else "failed",
            "目录可读取" if readable else "目录不可读取",
            None if readable else "当前服务进程必须能够读取仓库入口",
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
        remote_probe: subprocess.CompletedProcess[str] | None = None
        remote_ready = False
        if len(remote_urls) == 1:
            remote_probe = _run(
                ["git", "ls-remote", "--symref", remote_urls[0], "HEAD"],
                cwd=repository_root,
            )
            remote_ready = bool(
                remote_probe is not None
                and remote_probe.returncode == 0
                and remote_probe.stdout.strip()
            )
        result = _git_detection(
            detection,
            remote_urls=remote_urls,
            repository_root=repository_root,
            ready=readable and remote_ready,
            remote_only=False,
        )
        if not remote_urls:
            result["summary"] = "已识别 Git 工作区，但未配置权威 origin"
            checks.append(_check("workspace.remote", "failed", "未配置权威 origin"))
        elif len(remote_urls) > 1:
            result["summary"] = "已识别 Git 工作区，但无法确定唯一权威 origin"
            safe_remote_urls = [sanitize_remote_url(value) for value in remote_urls]
            checks.append(_check("workspace.remote", "failed", "origin 存在多个远端地址，无法确定权威来源", "；".join(safe_remote_urls)))
        elif remote_ready:
            checks.append(_check("workspace.remote", "ready", "Git 权威远端连接成功", sanitize_remote_url(remote_urls[0])))
        else:
            result["summary"] = "已识别 Git 工作区，但权威 origin 不可访问"
            checks.append(
                _check(
                    "workspace.remote",
                    "failed",
                    "Git 权威远端不可访问或没有 HEAD",
                    _safe_command_detail(remote_probe, remote_urls),
                )
            )
        return result

    svn_root_result = _run(["svn", "info", "--show-item", "wc-root"], cwd=path)
    svn_root_text = svn_root_result.stdout.strip() if svn_root_result is not None and svn_root_result.returncode == 0 else ""
    if svn_root_text:
        repository_root = Path(svn_root_text).resolve(strict=False)
        svn_url_result = _run(["svn", "info", "--show-item", "url"], cwd=repository_root)
        remote_url = (
            svn_url_result.stdout.strip()
            if svn_url_result is not None and svn_url_result.returncode == 0
            else ""
        )
        remote_probe = (
            _run(
                ["svn", "info", "--non-interactive", "--show-item", "revision", "--revision", "HEAD", remote_url],
                cwd=repository_root,
            )
            if remote_url
            else None
        )
        remote_ready = bool(
            remote_probe is not None
            and remote_probe.returncode == 0
            and remote_probe.stdout.strip()
        )
        detection.update(
            {
                "ready": readable and remote_ready,
                "vcsKind": "svn",
                "hostingKind": "none",
                "repositoryRoot": str(repository_root),
                "summary": "已识别为 SVN 工作副本",
            }
        )
        checks.append(_check("workspace.vcs", "ready", "SVN 工作副本可识别", str(repository_root)))
        if remote_url and remote_ready:
            detection["remoteUrl"] = sanitize_remote_url(remote_url)
            checks.append(_check("workspace.remote", "ready", "SVN 权威远端连接成功", sanitize_remote_url(remote_url)))
        elif remote_url:
            detection["summary"] = "已识别 SVN 工作副本，但权威远端不可访问"
            checks.append(
                _check(
                    "workspace.remote",
                    "failed",
                    "SVN 权威远端不可访问",
                    _safe_command_detail(remote_probe, [remote_url]),
                )
            )
        else:
            detection["summary"] = "已识别 SVN 工作副本，但无法读取远端地址"
            checks.append(_check("workspace.remote", "failed", "无法读取 SVN 工作副本地址", _command_detail(svn_url_result)))
        return detection

    details = [value for value in (_command_detail(inside_git), _command_detail(svn_root_result)) if value]
    checks.append(_check("workspace.vcs", "failed", "不是有效的 Git 或 SVN 工作目录", "；".join(details)))
    return detection


def available_final_actions(detection: WorkspaceDetection) -> set[str]:
    if not detection.get("ready"):
        return set()
    actions = {"patch"}
    if detection.get("vcsKind") == "git" and detection.get("hostingKind") == "gitlab":
        actions.add("gitlabPush")
    if detection.get("vcsKind") == "git" and detection.get("hostingKind") == "github":
        actions.add("githubPr")
    return actions
