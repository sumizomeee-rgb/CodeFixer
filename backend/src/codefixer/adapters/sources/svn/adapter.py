from __future__ import annotations

import shutil
from pathlib import Path

from codefixer.adapters.sources.common import CliSourceBase, SourceCommandError, patch_hash
from codefixer.application.ports.sources import CandidateChange, SourcePolicy, WorkspaceManifest
from codefixer.infrastructure.leases import LeaseStore


class SvnSourceAdapter(CliSourceBase):
    source_type = "svn"

    def __init__(
        self,
        working_copy: Path,
        command_prefix: list[str],
        leases: LeaseStore,
        runner=None,
    ) -> None:
        super().__init__(command_prefix, runner)
        self.working_copy = working_copy.resolve()
        self.leases = leases

    @property
    def lease_key(self) -> str:
        return f"svn-working-copy:{self.working_copy}"

    def current_revision(self) -> str:
        revision = self._run(["info", "--show-item", "revision"], cwd=self.working_copy).stdout.strip()
        if not revision:
            raise SourceCommandError("svn current revision is empty")
        return revision

    def prepare(
        self,
        *,
        source_id: str,
        run_id: str,
        workspace_path: Path,
        base_revision: str | None = None,
    ) -> WorkspaceManifest:
        self.leases.acquire(self.lease_key, run_id)
        try:
            status = self._run(["status"], cwd=self.working_copy).stdout
            if status.strip():
                raise SourceCommandError("SVN working copy is not clean before task start")
            self._run(["cleanup"], cwd=self.working_copy)
            self._run(["update"], cwd=self.working_copy, timeout=600)
            revision = self._run(["info", "--show-item", "revision"], cwd=self.working_copy).stdout.strip()
            if not revision:
                raise SourceCommandError("SVN base revision is empty")
            if base_revision is not None and revision != base_revision:
                raise SourceCommandError(f"SVN baseline changed: {base_revision} != {revision}")
            return WorkspaceManifest(
                source_type="svn",
                source_id=source_id,
                repository_path=self.working_copy,
                workspace_path=self.working_copy,
                base_revision=revision,
                lease_key=self.lease_key,
                lease_owner=run_id,
            )
        except Exception:
            self.leases.release(self.lease_key, run_id)
            raise

    def collect_change(self, manifest: WorkspaceManifest, policy: SourcePolicy) -> CandidateChange:
        status = self._run(["status"], cwd=manifest.workspace_path).stdout
        changed: list[str] = []
        operations: list[tuple[str, str]] = []
        for line in status.splitlines():
            if not line.strip() or len(line) < 8:
                continue
            marker = line[0]
            if marker in {"M", "A", "D", "R", "!", "?", "~"}:
                path = line[7:].strip().replace("\\", "/")
                if path:
                    changed.append(path)
                    operation = {"A": "add", "D": "delete", "?": "add"}.get(marker, "modify")
                    operations.append((path, operation))
        patch = self._run(["diff", "--git"], cwd=manifest.workspace_path).stdout
        unauthorized = tuple(path for path in changed if not policy.authorize(path))
        return CandidateChange(
            base_revision=manifest.base_revision,
            patch_text=patch,
            patch_sha256=patch_hash(patch),
            changed_paths=tuple(changed),
            unauthorized_paths=unauthorized,
            operations=tuple(operations),
        )

    def restore_candidate(self, manifest: WorkspaceManifest, candidate: CandidateChange) -> None:
        raise SourceCommandError("SVN verification mutated the working copy; candidate replay is unavailable")

    def cleanup(self, manifest: WorkspaceManifest) -> None:
        try:
            if manifest.workspace_path.exists():
                status = self._run(["status"], cwd=manifest.workspace_path, allow_failure=True).stdout
                self._run(["revert", "-R", "."], cwd=manifest.workspace_path, allow_failure=True)
                for line in status.splitlines():
                    if line.startswith("?") and len(line) >= 8:
                        relative = line[7:].strip()
                        target = (manifest.workspace_path / relative).resolve()
                        try:
                            target.relative_to(manifest.workspace_path.resolve())
                        except ValueError:
                            continue
                        if target.is_dir():
                            shutil.rmtree(target, ignore_errors=True)
                        else:
                            target.unlink(missing_ok=True)
                self._run(["cleanup"], cwd=manifest.workspace_path, allow_failure=True)
        finally:
            if manifest.lease_key and manifest.lease_owner:
                self.leases.release(manifest.lease_key, manifest.lease_owner)
