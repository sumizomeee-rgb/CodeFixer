from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from codefixer.adapters.sources.svn import SvnSourceAdapter


def svn(cwd: Path, *args: str) -> str:
    result = subprocess.run(["svn", *args], cwd=cwd, check=True, text=True, capture_output=True)
    return result.stdout.strip()


@pytest.mark.skipif(shutil.which("svn") is None or shutil.which("svnadmin") is None, reason="SVN CLI 不可用")
def test_svn_remote_baseline_ignores_dirty_working_copy_and_uses_isolated_checkout(tmp_path: Path) -> None:
    remote = tmp_path / "remote"
    subprocess.run(["svnadmin", "create", str(remote)], check=True, capture_output=True)
    remote_url = remote.as_uri()
    subprocess.run(["svn", "mkdir", f"{remote_url}/trunk", "-m", "create trunk"], check=True, capture_output=True)

    seed = tmp_path / "seed"
    working_copy = tmp_path / "working-copy"
    subprocess.run(["svn", "checkout", f"{remote_url}/trunk", str(seed)], check=True, capture_output=True)
    (seed / "app.py").write_text("value = 1\n", encoding="utf-8")
    svn(seed, "add", "app.py")
    svn(seed, "commit", "-m", "initial")
    subprocess.run(["svn", "checkout", f"{remote_url}/trunk", str(working_copy)], check=True, capture_output=True)
    local_revision = svn(working_copy, "info", "--show-item", "revision")
    (working_copy / "app.py").write_text("dirty local value\n", encoding="utf-8")

    (seed / "app.py").write_text("value = 2\n", encoding="utf-8")
    svn(seed, "commit", "-m", "remote update")
    remote_revision = svn(seed, "info", "--show-item", "revision", "--revision", "HEAD", f"{remote_url}/trunk")
    assert remote_revision != local_revision

    adapter = SvnSourceAdapter(working_copy, ["svn"])
    assert adapter.refresh_and_current_revision() == remote_revision
    workspace = tmp_path / "workspaces" / "modification"
    manifest = adapter.prepare(source_id="source-1", run_id="run-1", workspace_path=workspace)
    try:
        assert manifest.base_revision == remote_revision
        assert (workspace / "app.py").read_text(encoding="utf-8") == "value = 2\n"
        assert (working_copy / "app.py").read_text(encoding="utf-8") == "dirty local value\n"
        assert svn(working_copy, "info", "--show-item", "revision") == local_revision
    finally:
        adapter.cleanup(manifest)


@pytest.mark.skipif(shutil.which("svn") is None or shutil.which("svnadmin") is None, reason="SVN CLI 不可用")
def test_svn_working_copy_baseline_freezes_local_revision_without_update(tmp_path: Path) -> None:
    remote = tmp_path / "remote"
    subprocess.run(["svnadmin", "create", str(remote)], check=True, capture_output=True)
    remote_url = remote.as_uri()
    subprocess.run(["svn", "mkdir", f"{remote_url}/trunk", "-m", "create trunk"], check=True, capture_output=True)

    seed = tmp_path / "seed"
    working_copy = tmp_path / "working-copy"
    subprocess.run(["svn", "checkout", f"{remote_url}/trunk", str(seed)], check=True, capture_output=True)
    (seed / "app.py").write_text("value = 1\n", encoding="utf-8")
    svn(seed, "add", "app.py")
    svn(seed, "commit", "-m", "initial")
    subprocess.run(["svn", "checkout", f"{remote_url}/trunk", str(working_copy)], check=True, capture_output=True)
    local_revision = svn(working_copy, "info", "--show-item", "revision")

    (seed / "app.py").write_text("value = 2\n", encoding="utf-8")
    svn(seed, "commit", "-m", "remote update")

    adapter = SvnSourceAdapter(working_copy, ["svn"], baseline_source="working_copy")
    workspace = tmp_path / "workspaces" / "localization"
    manifest = adapter.prepare(source_id="source-2", run_id="run-2", workspace_path=workspace)
    try:
        assert manifest.base_revision == local_revision
        assert (workspace / "app.py").read_text(encoding="utf-8") == "value = 1\n"
        assert svn(working_copy, "info", "--show-item", "revision") == local_revision
    finally:
        adapter.cleanup(manifest)


@pytest.mark.skipif(shutil.which("svn") is None or shutil.which("svnadmin") is None, reason="SVN CLI 不可用")
def test_svn_adapter_accepts_remote_url_without_working_copy(tmp_path: Path) -> None:
    remote = tmp_path / "remote"
    subprocess.run(["svnadmin", "create", str(remote)], check=True, capture_output=True)
    remote_url = remote.as_uri()
    subprocess.run(["svn", "mkdir", f"{remote_url}/trunk", "-m", "create trunk"], check=True, capture_output=True)

    adapter = SvnSourceAdapter(None, ["svn"], remote_url=f"{remote_url}/trunk")
    revision = adapter.refresh_and_current_revision()
    workspace = tmp_path / "workspaces" / "remote"
    manifest = adapter.prepare(source_id="source-3", run_id="run-3", workspace_path=workspace, base_revision=revision)
    try:
        assert manifest.base_revision == revision
        assert workspace.is_dir()
    finally:
        adapter.cleanup(manifest)
