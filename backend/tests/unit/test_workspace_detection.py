from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

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
def test_detect_git_workspace__derives_hosting_and_actions(tmp_path: Path, remote: str, hosting: str, actions: set[str]):
    repository = tmp_path / "repository"
    nested = repository / "src" / "feature"
    nested.mkdir(parents=True)
    git(repository, "init", "-q")
    git(repository, "remote", "add", "origin", remote)

    result = detect_workspace(str(nested))

    assert result["ready"] is True
    assert result["vcsKind"] == "git"
    assert result["hostingKind"] == hosting
    assert result["repositoryRoot"] == str(repository.resolve())
    assert result["remoteUrl"] == remote
    assert available_final_actions(result) == actions


def test_detect_workspace__rejects_plain_directory(tmp_path: Path):
    result = detect_workspace(str(tmp_path))

    assert result["ready"] is False
    assert result["vcsKind"] == "unknown"
    assert result["hostingKind"] == "none"
    assert any(check["id"] == "workspace.vcs" and check["status"] == "failed" for check in result["checks"])
    assert available_final_actions(result) == set()


def test_remote_url__never_exposes_embedded_credentials():
    assert sanitize_remote_url("https://oauth2:secret@gitlab.com/company/project.git?token=secret") == "https://gitlab.com/company/project.git"


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
    assert available_final_actions(result) == {"patch"}
