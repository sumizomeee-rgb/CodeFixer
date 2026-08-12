from __future__ import annotations

import shutil
from pathlib import Path

from codefixer.adapters.sources.common import CliSourceBase, SourceCommandError, patch_hash
from codefixer.application.ports.sources import CandidateChange, SourcePolicy, WorkspaceManifest


class GitSourceAdapter(CliSourceBase):
    source_type = "git"

    def __init__(self, repository_path: Path, command_prefix: list[str], runner=None):
        super().__init__(command_prefix, runner)
        self.repository_path = repository_path.resolve()

    def current_revision(self) -> str:
        revision = self._run(["rev-parse", "HEAD"], cwd=self.repository_path).stdout.strip()
        if not revision:
            raise SourceCommandError("git current revision is empty")
        return revision

    def prepare(
        self,
        *,
        source_id: str,
        run_id: str,
        workspace_path: Path,
        base_revision: str | None = None,
    ) -> WorkspaceManifest:
        if workspace_path.exists():
            raise SourceCommandError(f"workspace already exists: {workspace_path}")
        base = base_revision or self._run(["rev-parse", "HEAD"], cwd=self.repository_path).stdout.strip()
        if not base:
            raise SourceCommandError("git base revision is empty")
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            ["worktree", "add", "--detach", "--lock", "--reason", f"codefixer:{run_id}", str(workspace_path), base],
            cwd=self.repository_path,
        )
        actual = self._run(["rev-parse", "HEAD"], cwd=workspace_path).stdout.strip()
        if actual != base:
            self.cleanup(WorkspaceManifest("git", source_id, self.repository_path, workspace_path, base))
            raise SourceCommandError(f"git worktree baseline mismatch: {base} != {actual}")
        return WorkspaceManifest(
            source_type="git",
            source_id=source_id,
            repository_path=self.repository_path,
            workspace_path=workspace_path.resolve(),
            base_revision=base,
        )

    def collect_change(self, manifest: WorkspaceManifest, policy: SourcePolicy) -> CandidateChange:
        current = self._run(["rev-parse", "HEAD"], cwd=manifest.workspace_path).stdout.strip()
        if current != manifest.base_revision:
            raise SourceCommandError("agent changed git HEAD; repair must remain on frozen baseline")
        self._run(["add", "-A", "--", "."], cwd=manifest.workspace_path)
        names_raw = self._run(
            ["diff", "--cached", "--name-only", "-z", manifest.base_revision, "--"],
            cwd=manifest.workspace_path,
        ).stdout
        changed = tuple(item for item in names_raw.split("\0") if item)
        patch = self._run(
            ["diff", "--cached", "--binary", "--no-ext-diff", manifest.base_revision, "--"],
            cwd=manifest.workspace_path,
        ).stdout
        status_text = self._run(
            ["diff", "--cached", "--name-status", "--find-renames", manifest.base_revision, "--"],
            cwd=manifest.workspace_path,
        ).stdout
        operations: list[tuple[str, str]] = []
        for line in status_text.splitlines():
            fields = line.split("\t")
            if len(fields) < 2:
                continue
            code = fields[0]
            if code.startswith("R") and len(fields) >= 3:
                operations.append((fields[2], "rename"))
            else:
                operation = {"A": "add", "D": "delete", "M": "modify"}.get(code[:1], "modify")
                operations.append((fields[1], operation))
        unauthorized = tuple(path for path in changed if not policy.authorize(path))
        return CandidateChange(
            base_revision=manifest.base_revision,
            patch_text=patch,
            patch_sha256=patch_hash(patch),
            changed_paths=changed,
            unauthorized_paths=unauthorized,
            operations=tuple(operations),
        )

    def restore_candidate(self, manifest: WorkspaceManifest, candidate: CandidateChange) -> None:
        self._run(["reset", "--hard", manifest.base_revision], cwd=manifest.workspace_path)
        self._run(["clean", "-fd"], cwd=manifest.workspace_path)
        if not candidate.patch_text:
            return
        patch_file = manifest.workspace_path.parent / f".{manifest.workspace_path.name}.candidate.patch"
        patch_file.write_text(candidate.patch_text, encoding="utf-8")
        try:
            self._run(["apply", "--index", "--binary", str(patch_file)], cwd=manifest.workspace_path)
        finally:
            patch_file.unlink(missing_ok=True)

    def cleanup(self, manifest: WorkspaceManifest) -> None:
        if manifest.workspace_path.exists():
            self._run(["worktree", "unlock", str(manifest.workspace_path)], cwd=self.repository_path, allow_failure=True)
            result = self._run(
                ["worktree", "remove", "--force", str(manifest.workspace_path)],
                cwd=self.repository_path,
                allow_failure=True,
            )
            if result.exit_code != 0 and manifest.workspace_path.exists():
                shutil.rmtree(manifest.workspace_path, ignore_errors=True)
                self._run(["worktree", "prune"], cwd=self.repository_path, allow_failure=True)
