from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from codefixer.adapters.sources.git import GitSourceAdapter
from codefixer.adapters.sources.common import SourceCommandError
from codefixer.application.ports.sources import SourcePolicy


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


def test_git_workspace_isolated_diff_and_cleanup(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; repo.mkdir(); git(repo, "init"); git(repo, "config", "user.email", "test@codefixer.local"); git(repo, "config", "user.name", "CodeFixer Test")
    (repo / "src").mkdir(); (repo / "src/app.py").write_text("value = 1\n", encoding="utf-8"); git(repo, "add", "."); git(repo, "commit", "-m", "base"); base = git(repo, "rev-parse", "HEAD")
    workspace = tmp_path / "workspaces/run-1"; adapter = GitSourceAdapter(repo, ["git"]); manifest = adapter.prepare(source_id="source-1", run_id="run-1", workspace_path=workspace)
    assert manifest.base_revision == base; assert git(repo, "status", "--porcelain") == ""
    (workspace / "src/app.py").write_text("value = 2\n", encoding="utf-8"); (workspace / "src/new.py").write_text("created = True\n", encoding="utf-8")
    change = adapter.collect_change(manifest, SourcePolicy(allowed_roots=("src",), allowed_extensions=(".py",)))
    assert set(change.changed_paths) == {"src/app.py", "src/new.py"}; assert not change.unauthorized_paths; assert "value = 2" in change.patch_text; assert "created = True" in change.patch_text; assert git(repo, "status", "--porcelain") == ""
    adapter.cleanup(manifest); assert not workspace.exists(); assert "run-1" not in git(repo, "worktree", "list", "--porcelain")


def test_git_workspace_reports_unauthorized_change(tmp_path: Path) -> None:
    repo = tmp_path / "repo"; repo.mkdir(); git(repo, "init"); git(repo, "config", "user.email", "test@codefixer.local"); git(repo, "config", "user.name", "CodeFixer Test")
    (repo / "src").mkdir(); (repo / "docs").mkdir(); (repo / "src/app.py").write_text("ok = True\n", encoding="utf-8"); (repo / "docs/secret.txt").write_text("old\n", encoding="utf-8"); git(repo, "add", "."); git(repo, "commit", "-m", "base")
    adapter = GitSourceAdapter(repo, ["git"]); manifest = adapter.prepare(source_id="source-1", run_id="run-2", workspace_path=tmp_path / "wt")
    try:
        (manifest.workspace_path / "docs/secret.txt").write_text("changed\n", encoding="utf-8"); change = adapter.collect_change(manifest, SourcePolicy(allowed_roots=("src",))); assert change.unauthorized_paths == ("docs/secret.txt",); assert not change.valid
    finally:
        adapter.cleanup(manifest)


def test_git_restore_candidate_survives_crlf_checkout_and_verification_side_effects(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@codefixer.local")
    git(repo, "config", "user.name", "CodeFixer Test")
    git(repo, "config", "core.autocrlf", "true")
    (repo / "src").mkdir()
    (repo / "src/app.py").write_bytes(b"value = 1\n")
    (repo / "src/obsolete.py").write_bytes(b"obsolete = True\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")

    adapter = GitSourceAdapter(repo, ["git"])
    manifest = adapter.prepare(
        source_id="source-1",
        run_id="run-crlf",
        workspace_path=tmp_path / "workspaces/run-crlf",
    )
    policy = SourcePolicy(allowed_roots=("src",), allowed_extensions=(".py",))
    try:
        assert b"\r\n" in (manifest.workspace_path / "src/app.py").read_bytes()
        (manifest.workspace_path / "src/app.py").write_bytes(b"value = 2\n")
        (manifest.workspace_path / "src/obsolete.py").unlink()
        (manifest.workspace_path / "src/new.py").write_bytes(b"created = True\n")
        candidate = adapter.collect_change(manifest, policy)

        (manifest.workspace_path / "src/app.py").write_bytes(b"value = 999\n")
        side_effect = manifest.workspace_path / "src/__pycache__/app.pyc"
        side_effect.parent.mkdir()
        side_effect.write_bytes(b"verification side effect")

        adapter.restore_candidate(manifest, candidate)
        restored = adapter.collect_change(manifest, policy)

        assert restored.patch_sha256 == candidate.patch_sha256
        assert restored.changed_paths == candidate.changed_paths
        assert restored.operations == candidate.operations
        assert not side_effect.exists()
        assert not (manifest.workspace_path / "src/obsolete.py").exists()
    finally:
        adapter.cleanup(manifest)


def test_git_restore_candidate_survives_crlf_stored_in_repository(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init")
    git(repo, "config", "user.email", "test@codefixer.local")
    git(repo, "config", "user.name", "CodeFixer Test")
    git(repo, "config", "core.autocrlf", "false")
    (repo / "app.py").write_bytes(b"def value():\r\n    return 1\r\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base with stored CRLF")

    adapter = GitSourceAdapter(repo, ["git"])
    manifest = adapter.prepare(
        source_id="source-1",
        run_id="run-stored-crlf",
        workspace_path=tmp_path / "workspaces/run-stored-crlf",
    )
    policy = SourcePolicy(allowed_roots=(".",), allowed_extensions=(".py",))
    try:
        (manifest.workspace_path / "app.py").write_bytes(b"def value():\r\n    return 2\r\n")
        candidate = adapter.collect_change(manifest, policy)
        side_effect = manifest.workspace_path / "__pycache__/app.pyc"
        side_effect.parent.mkdir()
        side_effect.write_bytes(b"verification side effect")

        adapter.restore_candidate(manifest, candidate)
        restored = adapter.collect_change(manifest, policy)

        assert restored.patch_sha256 == candidate.patch_sha256
        assert restored.changed_paths == candidate.changed_paths
        assert restored.operations == candidate.operations
        assert not side_effect.exists()
    finally:
        adapter.cleanup(manifest)


def test_git_refresh_uses_remote_branch_without_touching_dirty_worktree(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    seed = tmp_path / "seed"
    local = tmp_path / "local"
    remote.mkdir()
    git(remote, "init", "--bare")
    seed.mkdir()
    git(seed, "init")
    git(seed, "config", "user.email", "test@codefixer.local")
    git(seed, "config", "user.name", "CodeFixer Test")
    (seed / "app.py").write_text("value = 1\n", encoding="utf-8")
    git(seed, "add", ".")
    git(seed, "commit", "-m", "initial")
    branch = git(seed, "branch", "--show-current")
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "-u", "origin", branch)
    subprocess.run(["git", "clone", str(remote), str(local)], check=True, capture_output=True)

    (local / "app.py").write_text("dirty local value\n", encoding="utf-8")
    (seed / "app.py").write_text("value = 2\n", encoding="utf-8")
    git(seed, "add", ".")
    git(seed, "commit", "-m", "remote update")
    remote_revision = git(seed, "rev-parse", "HEAD")
    git(seed, "push", "origin", branch)

    adapter = GitSourceAdapter(local, ["git"])

    assert adapter.refresh_and_current_revision() == remote_revision
    assert (local / "app.py").read_text(encoding="utf-8") == "dirty local value\n"

    git(local, "switch", "-c", "local-only")
    with pytest.raises(SourceCommandError, match="origin does not contain current branch"):
        adapter.refresh_and_current_revision()


def test_git_refresh_does_not_fall_back_to_local_head_when_fetch_fails(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.email", "test@codefixer.local")
    git(repository, "config", "user.name", "CodeFixer Test")
    (repository / "app.py").write_text("value = 1\n", encoding="utf-8")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "local only")
    git(repository, "remote", "add", "origin", str(tmp_path / "missing.git"))

    with pytest.raises(SourceCommandError):
        GitSourceAdapter(repository, ["git"]).refresh_and_current_revision()
