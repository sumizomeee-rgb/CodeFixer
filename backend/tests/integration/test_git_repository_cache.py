from __future__ import annotations

import hashlib
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from codefixer.application.services.git_repository_cache import (
    GitRepositoryCacheError,
    ensure_git_repository,
)


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def create_remote(tmp_path: Path) -> tuple[Path, Path]:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    remote.mkdir()
    seed.mkdir()
    git(remote, "init", "--bare", "-q")
    git(seed, "init", "-q", "-b", "main")
    git(seed, "config", "user.name", "Test")
    git(seed, "config", "user.email", "test@example.com")
    (seed / "README.md").write_text("first\n", encoding="utf-8")
    git(seed, "add", "README.md")
    git(seed, "commit", "-q", "-m", "first")
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "-q", "-u", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    return remote, seed


def test_ensure_git_repository__creates_stable_worktree_ready_cache(tmp_path: Path):
    remote, _ = create_remote(tmp_path)
    cache_root = tmp_path / "cache"
    remote_url = str(remote)

    repository = ensure_git_repository(remote_url, cache_root, ["git"])

    expected_key = hashlib.sha256(remote_url.encode("utf-8")).hexdigest()
    assert repository == (cache_root / expected_key).resolve()
    assert git(repository, "remote", "get-url", "origin") == remote_url
    assert git(repository, "rev-parse", "--is-bare-repository") == "false"
    assert git(repository, "rev-parse", "origin/main")

    workspace = tmp_path / "task-worktree"
    git(repository, "worktree", "add", "--detach", str(workspace), "origin/main")
    assert (workspace / "README.md").read_text(encoding="utf-8") == "first\n"


def test_ensure_git_repository__does_not_fetch_existing_cache(tmp_path: Path):
    remote, seed = create_remote(tmp_path)
    repository = ensure_git_repository(str(remote), tmp_path / "cache", ["git"])
    cached_revision = git(repository, "rev-parse", "origin/main")

    (seed / "README.md").write_text("second\n", encoding="utf-8")
    git(seed, "add", "README.md")
    git(seed, "commit", "-q", "-m", "second")
    git(seed, "push", "-q", "origin", "main")

    same_repository = ensure_git_repository(str(remote), tmp_path / "cache", ["git"])

    assert same_repository == repository
    assert git(repository, "rev-parse", "origin/main") == cached_revision
    assert git(seed, "rev-parse", "HEAD") != cached_revision


def test_ensure_git_repository__concurrent_first_use_publishes_one_valid_cache(
    tmp_path: Path,
):
    remote, _ = create_remote(tmp_path)
    cache_root = tmp_path / "cache"

    with ThreadPoolExecutor(max_workers=4) as executor:
        repositories = list(
            executor.map(
                lambda _: ensure_git_repository(str(remote), cache_root, ["git"]),
                range(4),
            )
        )

    assert len(set(repositories)) == 1
    assert git(repositories[0], "remote", "get-url", "origin") == str(remote)
    assert not list(cache_root.glob(".tmp-*/repository"))


def test_ensure_git_repository__never_exposes_credential_url_in_errors(tmp_path: Path):
    secret = "credential-must-not-leak"
    remote_url = f"https://oauth2:{secret}@127.0.0.1:1/missing.git"

    with pytest.raises(GitRepositoryCacheError) as captured:
        ensure_git_repository(remote_url, tmp_path / "cache", ["git"])

    message = str(captured.value)
    assert secret not in message
    assert remote_url not in message


def test_ensure_git_repository__rejects_origin_mismatch_without_exposing_it(tmp_path: Path):
    remote, _ = create_remote(tmp_path)
    cache_root = tmp_path / "cache"
    repository = ensure_git_repository(str(remote), cache_root, ["git"])
    secret = "changed-origin-secret"
    changed_origin = f"https://oauth2:{secret}@example.invalid/project.git"
    git(repository, "remote", "set-url", "origin", changed_origin)

    with pytest.raises(GitRepositoryCacheError) as captured:
        ensure_git_repository(str(remote), cache_root, ["git"])

    message = str(captured.value)
    assert "origin" in message
    assert secret not in message
    assert changed_origin not in message
