from pathlib import Path

import pytest

from codefixer.adapters.sources.directory import DirectoryReadOnlySourceAdapter
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
