from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from codefixer.adapters.sources.common import CliSourceBase, SourceCommandError, patch_hash
from codefixer.application.ports.sources import CandidateChange, SourcePolicy, WorkspaceManifest
from codefixer.infrastructure.process_runner import ProcessRunner


class SvnSourceAdapter(CliSourceBase):
    source_type: str = "svn"

    def __init__(
        self,
        working_copy: Path | None,
        command_prefix: list[str],
        runner: ProcessRunner | None = None,
        *,
        remote_url: str | None = None,
        baseline_source: Literal["remote", "working_copy"] = "remote",
    ) -> None:
        super().__init__(command_prefix, runner)
        if working_copy is None and not remote_url:
            raise ValueError("SVN source requires a working copy or remote URL")
        if baseline_source == "working_copy" and working_copy is None:
            raise ValueError("SVN working-copy baseline requires a working copy")
        self.working_copy = working_copy.resolve() if working_copy is not None else None
        self.remote_url = remote_url.strip() if remote_url else None
        self.baseline_source = baseline_source

    @property
    def command_cwd(self) -> Path:
        return self.working_copy or Path.cwd()

    def repository_url(self) -> str:
        if self.remote_url:
            return self.remote_url
        if self.working_copy is None:
            raise SourceCommandError("SVN working copy is unavailable")
        repository_url = self._run(
            ["info", "--show-item", "url"], cwd=self.working_copy
        ).stdout.strip()
        if not repository_url:
            raise SourceCommandError("SVN working copy URL is empty")
        self.remote_url = repository_url
        return repository_url

    def current_revision(self) -> str:
        if self.working_copy is None:
            return self.remote_revision()
        revision = self._run(["info", "--show-item", "revision"], cwd=self.working_copy).stdout.strip()
        if not revision:
            raise SourceCommandError("svn current revision is empty")
        return revision

    def remote_revision(self) -> str:
        revision = self._run(
            [
                "info",
                "--non-interactive",
                "--show-item",
                "revision",
                "--revision",
                "HEAD",
                self.repository_url(),
            ],
            cwd=self.command_cwd,
            timeout=600,
        ).stdout.strip()
        if not revision:
            raise SourceCommandError("svn remote revision is empty")
        return revision

    def refresh_and_current_revision(self) -> str:
        """查询权威远端版本，不检查或更新用户的 working copy。"""
        return self.remote_revision()

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
        revision = base_revision
        if revision is None:
            revision = self.remote_revision() if self.baseline_source == "remote" else self.current_revision()
        workspace_path.parent.mkdir(parents=True, exist_ok=True)
        self._run(
            [
                "checkout",
                "--non-interactive",
                "--revision",
                revision,
                self.repository_url(),
                str(workspace_path),
            ],
            cwd=self.command_cwd,
            timeout=600,
        )
        actual = self._run(
            ["info", "--show-item", "revision"], cwd=workspace_path
        ).stdout.strip()
        if actual != revision:
            shutil.rmtree(workspace_path, ignore_errors=True)
            raise SourceCommandError(
                f"SVN isolated baseline mismatch: {revision} != {actual}"
            )
        return WorkspaceManifest(
            source_type="svn",
            source_id=source_id,
            repository_path=self.working_copy or workspace_path.parent.resolve(),
            workspace_path=workspace_path.resolve(),
            base_revision=revision,
        )

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
        shutil.rmtree(manifest.workspace_path, ignore_errors=True)
