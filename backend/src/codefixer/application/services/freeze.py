from __future__ import annotations

import hashlib
from pathlib import Path

from codefixer.application.ports.sources import CandidateChange, WorkspaceManifest
from codefixer.protocols import ArtifactStore, StoredArtifact


def _file_hash(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def freeze_change(
    *,
    artifacts: ArtifactStore,
    task_id: str,
    run_id: str,
    manifest: WorkspaceManifest,
    candidate: CandidateChange,
    verification: StoredArtifact,
    coding_result: StoredArtifact,
    config_sha256: str,
    change_version: int = 1,
) -> tuple[StoredArtifact, StoredArtifact]:
    freeze_root = artifacts.run_root(task_id, run_id) / "freeze-change"
    patch = artifacts.write_text(freeze_root / "change.patch", candidate.patch_text)
    operations = dict(candidate.operations)
    files = []
    for relative in candidate.changed_paths:
        operation = operations.get(relative, "modify")
        source_file = manifest.workspace_path / relative
        content_sha256 = None if operation == "delete" else _file_hash(source_file)
        if operation != "delete":
            if content_sha256 is None:
                raise FileNotFoundError(f"changed file missing while freezing: {relative}")
            snapshot = artifacts.write_bytes(freeze_root / "files" / relative, source_file.read_bytes())
            if snapshot.sha256 != content_sha256:
                raise RuntimeError(f"frozen file hash mismatch: {relative}")
        files.append(
            {
                "path": relative,
                "operation": operation,
                "content_sha256": content_sha256,
            }
        )
    change_manifest = {
        "schema_version": 1,
        "change_version": change_version,
        "modification_source": {
            "id": manifest.source_id,
            "base_revision": manifest.base_revision,
        },
        "diff": {"path": patch.path.name, "sha256": patch.sha256},
        "files": files,
        "source_commits": [],
        "verification_sha256": verification.sha256,
        "coding_result_sha256": coding_result.sha256,
        "config_sha256": config_sha256,
    }
    manifest_artifact = artifacts.write_json(
        freeze_root / "change-manifest.json",
        change_manifest,
        schema_name="change-manifest",
        copy_schema=True,
    )
    return patch, manifest_artifact
