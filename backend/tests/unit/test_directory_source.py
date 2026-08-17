from pathlib import Path

import pytest

from codefixer.adapters.sources.directory import (
    DirectReadOnlySourceAdapter,
    DirectoryReadOnlySourceAdapter,
)
from codefixer.application.ports.sources import SourcePolicy


def test_plain_localization_directory_is_snapshotted_and_cleaned(tmp_path: Path) -> None:
    source = tmp_path / "knowledge"
    source.mkdir()
    (source / "notes.md").write_text("frozen evidence\n", encoding="utf-8")
    adapter = DirectoryReadOnlySourceAdapter(source)

    manifest = adapter.prepare(
        source_id="knowledge",
        run_id="run-1:discovery",
        workspace_path=tmp_path / "snapshot",
    )

    assert manifest.source_type == "directory"
    assert (manifest.workspace_path / "notes.md").read_text(encoding="utf-8") == "frozen evidence\n"
    assert manifest.base_revision.startswith("directory-")
    with pytest.raises(PermissionError):
        adapter.collect_change(manifest, SourcePolicy())
    adapter.cleanup(manifest)
    assert not manifest.workspace_path.exists()


def test_plain_localization_snapshot_rejects_stale_revision(tmp_path: Path) -> None:
    source = tmp_path / "knowledge"
    source.mkdir()
    (source / "notes.md").write_text("new\n", encoding="utf-8")
    adapter = DirectoryReadOnlySourceAdapter(source)

    with pytest.raises(ValueError, match="changed before snapshot"):
        adapter.prepare(
            source_id="knowledge",
            run_id="run-2:discovery",
            workspace_path=tmp_path / "snapshot",
            base_revision="directory-stale",
        )


def test_direct_localization_directory_is_used_in_place_and_never_deleted(tmp_path: Path) -> None:
    source = tmp_path / "knowledge"
    source.mkdir()
    note = source / "notes.md"
    note.write_text("live evidence\n", encoding="utf-8")
    revision = "git-abc123"
    adapter = DirectReadOnlySourceAdapter(
        source, lambda: revision, source_type="git"
    )

    manifest = adapter.prepare(
        source_id="knowledge",
        run_id="run-direct:discovery",
        workspace_path=tmp_path / "must-not-be-created",
    )

    assert manifest.workspace_path == source.resolve()
    assert manifest.repository_path == source.resolve()
    assert manifest.source_type == "git"
    assert manifest.base_revision == revision
    assert not (tmp_path / "must-not-be-created").exists()
    adapter.cleanup(manifest)
    assert note.read_text(encoding="utf-8") == "live evidence\n"
