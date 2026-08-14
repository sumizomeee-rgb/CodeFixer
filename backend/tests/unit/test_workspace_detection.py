from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

import codefixer.application.services.workspace_detection as workspace_detection
from codefixer.application.services.workspace_detection import available_final_actions, detect_workspace, sanitize_remote_url


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


@pytest.mark.parametrize(
    ("remote", "hosting", "actions"),
    [
        ("git@github.com:company/project.git", "github", {"patch", "githubPr"}),
        ("https://gitlab.com/company/project.git", "gitlab", {"patch", "gitlabPush"}),
        ("ssh://git@example.test/company/project.git", "other", {"patch"}),
    ],
)
def test_detect_git_workspace__derives_hosting_and_actions(
    tmp_path: Path,
    monkeypatch,
    remote: str,
    hosting: str,
    actions: set[str],
):
    repository = tmp_path / "repository"
    nested = repository / "src" / "feature"
    nested.mkdir(parents=True)
    git(repository, "init", "-q")
    git(repository, "remote", "add", "origin", remote)
    original_run = workspace_detection._run

    def connected_remote(command: list[str], *, cwd: Path, timeout: int = 10):
        if command[:2] == ["git", "ls-remote"]:
            return subprocess.CompletedProcess(command, 0, "ref: refs/heads/main\tHEAD\nabc\tHEAD\n", "")
        return original_run(command, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(workspace_detection, "_run", connected_remote)

    result = detect_workspace(str(nested))

    assert result["ready"] is True
    assert result["vcsKind"] == "git"
    assert result["hostingKind"] == hosting
    assert result["repositoryRoot"] == str(repository.resolve())
    assert result["remoteUrl"] == remote
    assert available_final_actions(result) == actions


def test_detect_git_workspace__only_reads_origin_when_worktree_is_dirty(tmp_path: Path, monkeypatch):
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "-q")
    git(repository, "remote", "add", "origin", "git@github.com:company/project.git")
    (repository / "untracked.txt").write_text("dirty\n", encoding="utf-8")
    original_run = workspace_detection._run

    def connected_remote(command: list[str], *, cwd: Path, timeout: int = 10):
        if command[:2] == ["git", "ls-remote"]:
            return subprocess.CompletedProcess(command, 0, "ref: refs/heads/main\tHEAD\nabc\tHEAD\n", "")
        return original_run(command, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(workspace_detection, "_run", connected_remote)

    result = detect_workspace(str(repository), location_type="local")

    assert result["ready"] is True
    assert result["locationType"] == "local"
    assert result["location"] == str(repository.resolve())
    assert result["remoteUrl"] == "git@github.com:company/project.git"


def test_detect_remote_git_repository(tmp_path: Path):
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    remote.mkdir()
    git(remote, "init", "--bare", "-q")
    seed.mkdir()
    git(seed, "init", "-q")
    subprocess.run(["git", "-C", str(seed), "config", "user.email", "test@codefixer.local"], check=True)
    subprocess.run(["git", "-C", str(seed), "config", "user.name", "CodeFixer Test"], check=True)
    (seed / "app.py").write_text("value = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(seed), "add", "."], check=True)
    subprocess.run(["git", "-C", str(seed), "commit", "-m", "initial"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(seed), "push", remote.as_uri(), "HEAD:main"], check=True, capture_output=True)
    subprocess.run(["git", "--git-dir", str(remote), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)

    result = detect_workspace(remote.as_uri(), location_type="remote")

    assert result["ready"] is True
    assert result["locationType"] == "remote"
    assert result["location"] == remote.as_uri()
    assert result["remoteUrl"] == remote.as_uri()
    assert result["vcsKind"] == "git"
    assert "repositoryRoot" not in result


def test_detect_git_workspace__rejects_missing_authoritative_origin(tmp_path: Path):
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "-q")

    result = detect_workspace(str(repository), location_type="local")

    assert result["ready"] is False
    assert "remoteUrl" not in result
    assert any(check["id"] == "workspace.remote" and check["status"] == "failed" for check in result["checks"])


def test_detect_git_workspace__sanitizes_unreachable_origin_diagnostics(tmp_path: Path, monkeypatch):
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init", "-q")
    secret_remote = "https://oauth2:secret@example.test/company/project.git"
    git(repository, "remote", "add", "origin", secret_remote)
    original_run = workspace_detection._run

    def unreachable_remote(command: list[str], *, cwd: Path, timeout: int = 10):
        if command[:2] == ["git", "ls-remote"]:
            return subprocess.CompletedProcess(command, 128, "", f"fatal: repository '{secret_remote}' not found")
        return original_run(command, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(workspace_detection, "_run", unreachable_remote)

    result = detect_workspace(str(repository), location_type="local")
    serialized = repr(result)

    assert result["ready"] is False
    assert result["remoteUrl"] == "https://example.test/company/project.git"
    assert "secret" not in serialized
    assert "oauth2" not in serialized


def test_detect_workspace__rejects_plain_directory(tmp_path: Path):
    result = detect_workspace(str(tmp_path))

    assert result["ready"] is False
    assert result["vcsKind"] == "unknown"
    assert result["hostingKind"] == "none"
    assert any(check["id"] == "workspace.vcs" and check["status"] == "failed" for check in result["checks"])
    assert available_final_actions(result) == set()


def test_remote_url__never_exposes_embedded_credentials():
    assert sanitize_remote_url("https://oauth2:secret@gitlab.com/company/project.git?token=secret") == "https://gitlab.com/company/project.git"


def test_probe_gitlab_web_base__falls_back_to_self_hosted_sign_in_page(monkeypatch):
    def fake_get(url: str, **kwargs):
        del kwargs
        request = workspace_detection.httpx.Request("GET", url)
        if url.endswith("/-/health"):
            return workspace_detection.httpx.Response(404, text="Not Found", request=request)
        return workspace_detection.httpx.Response(
            200,
            text='<meta content="GitLab" property="og:site_name"><title>Sign in · GitLab</title>',
            request=request,
        )

    monkeypatch.setattr(workspace_detection.httpx, "get", fake_get)

    assert workspace_detection._probe_gitlab_web_base("git.company.test") == "https://git.company.test"


@pytest.mark.skipif(shutil.which("svn") is None or shutil.which("svnadmin") is None, reason="SVN CLI 不可用")
def test_detect_svn_workspace(tmp_path: Path):
    remote = tmp_path / "remote"
    working_copy = tmp_path / "working-copy"
    subprocess.run(["svnadmin", "create", str(remote)], check=True, capture_output=True)
    subprocess.run(["svn", "checkout", remote.as_uri(), str(working_copy)], check=True, capture_output=True)

    result = detect_workspace(str(working_copy))

    assert result["ready"] is True
    assert result["vcsKind"] == "svn"
    assert result["hostingKind"] == "none"
    assert result["repositoryRoot"] == str(working_copy.resolve())
    assert result["remoteUrl"] == remote.as_uri()
    assert available_final_actions(result) == {"patch"}


@pytest.mark.skipif(shutil.which("svn") is None or shutil.which("svnadmin") is None, reason="SVN CLI 不可用")
def test_detect_remote_svn_repository(tmp_path: Path):
    remote = tmp_path / "remote"
    subprocess.run(["svnadmin", "create", str(remote)], check=True, capture_output=True)

    result = detect_workspace(remote.as_uri(), location_type="remote")

    assert result["ready"] is True
    assert result["locationType"] == "remote"
    assert result["remoteUrl"] == remote.as_uri()
    assert result["vcsKind"] == "svn"
    assert "repositoryRoot" not in result
