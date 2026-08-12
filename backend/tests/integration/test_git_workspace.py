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
