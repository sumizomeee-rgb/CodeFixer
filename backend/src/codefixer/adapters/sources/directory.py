from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

from codefixer.application.ports.sources import CandidateChange, SourcePolicy, WorkspaceManifest


class DirectoryReadOnlySourceAdapter:
    """Create an immutable task-local snapshot of a plain localization directory."""

    source_type: str = "directory"

    def __init__(self, directory: Path) -> None:
        self.directory = directory.resolve()

    def current_revision(self) -> str:
        digest = hashlib.sha256()
        for root, directories, files in os.walk(self.directory, followlinks=False):
            directories[:] = sorted(
                item for item in directories if not (Path(root) / item).is_symlink()
            )
            for name in sorted(files):
                path = Path(root) / name
                if path.is_symlink():
                    continue
                relative = path.relative_to(self.directory).as_posix()
                stat = path.stat()
                digest.update(relative.encode("utf-8"))
                digest.update(str(stat.st_size).encode("ascii"))
                digest.update(str(stat.st_mtime_ns).encode("ascii"))
        return f"directory-{digest.hexdigest()}"

    def prepare(
        self,
        *,
        source_id: str,
        run_id: str,
        workspace_path: Path,
        base_revision: str | None = None,
    ) -> WorkspaceManifest:
        if workspace_path.exists():
            raise ValueError(f"workspace already exists: {workspace_path}")
        if not self.directory.is_dir():
            raise ValueError(f"localization directory does not exist: {self.directory}")
        revision = self.current_revision()
        if base_revision is not None and base_revision != revision:
            raise ValueError("localization directory changed before snapshot")
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self.directory, workspace_path, symlinks=True)
        return WorkspaceManifest(
            source_type="directory",
            source_id=source_id,
            repository_path=self.directory,
            workspace_path=workspace_path.resolve(),
            base_revision=revision,
        )

    def collect_change(
        self, manifest: WorkspaceManifest, policy: SourcePolicy
    ) -> CandidateChange:
        raise PermissionError("plain localization directories are read-only")

    def restore_candidate(
        self, manifest: WorkspaceManifest, candidate: CandidateChange
    ) -> None:
        raise PermissionError("plain localization directories are read-only")

    def cleanup(self, manifest: WorkspaceManifest) -> None:
        if manifest.workspace_path.exists():
            shutil.rmtree(manifest.workspace_path, ignore_errors=True)
