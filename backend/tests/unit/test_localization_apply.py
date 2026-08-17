from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from codefixer.application.services.localization_apply import (
    apply_frozen_change_to_localization,
)


def _fixture(tmp_path: Path) -> tuple[Path, dict, dict]:
    data = tmp_path / "data"
    localization = tmp_path / "localization"
    localization.mkdir()
    (localization / "src").mkdir()
    (localization / "src/changed.py").write_text("old\n", encoding="utf-8")
    (localization / "src/deleted.py").write_text("delete me\n", encoding="utf-8")
    run_root = data / "tasks/task-1/runs/run-1"
    frozen = run_root / "freeze-change/files/src/changed.py"
    frozen.parent.mkdir(parents=True)
    content = b"new\n"
    frozen.write_bytes(content)
    manifest = {
        "files": [
            {
                "path": "src/changed.py",
                "operation": "modify",
                "content_sha256": hashlib.sha256(content).hexdigest(),
            },
            {"path": "src/deleted.py", "operation": "delete", "content_sha256": None},
        ]
    }
    (run_root / "freeze-change/change-manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    (run_root / "snapshot").mkdir()
    project = {
        "id": "lua",
        "localizationSource": {"id": "lua-source", "path": str(localization)},
    }
    (run_root / "snapshot/config-snapshot.json").write_text(
        json.dumps({"project": project}), encoding="utf-8"
    )
    task = {
        "id": "task-1",
        "current_run_id": "run-1",
        "project_id": "lua",
        "status": "completed",
        "result": "changed",
    }
    return data, project, task


def test_apply_frozen_change_overwrites_and_deletes_localization_files(tmp_path: Path) -> None:
    data, project, task = _fixture(tmp_path)

    result = apply_frozen_change_to_localization(
        task=task, data_root=data, current_project=project
    )

    localization = Path(project["localizationSource"]["path"])
    assert (localization / "src/changed.py").read_text(encoding="utf-8") == "new\n"
    assert not (localization / "src/deleted.py").exists()
    assert result.copied == 1
    assert result.deleted == 1


def test_apply_frozen_change_rejects_changed_localization_directory(tmp_path: Path) -> None:
    data, project, task = _fixture(tmp_path)
    other = tmp_path / "other"
    other.mkdir()
    changed = {
        **project,
        "localizationSource": {"id": "lua-source", "path": str(other)},
    }

    with pytest.raises(ValueError, match="定位资料已变更"):
        apply_frozen_change_to_localization(
            task=task, data_root=data, current_project=changed
        )
