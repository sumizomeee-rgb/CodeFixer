from __future__ import annotations

import subprocess
from pathlib import Path

from codefixer.application.services.preflight import _git_delivery_health


def git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_gitlab_delivery_health_uses_local_repository_origin(tmp_path: Path):
    remote = tmp_path / "remote.git"
    repository = tmp_path / "repository"
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True)
    repository.mkdir()
    git(repository, "init")
    git(repository, "remote", "add", "origin", str(remote))

    healthy, summary = _git_delivery_health(str(remote), ["git"], cwd=repository)

    assert healthy is True
    assert str(remote) in summary
