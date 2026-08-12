from __future__ import annotations

import subprocess
from pathlib import Path

from codefixer.adapters.sources.git import GitSourceAdapter
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
