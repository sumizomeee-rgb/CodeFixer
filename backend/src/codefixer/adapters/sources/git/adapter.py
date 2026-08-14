from __future__ import annotations

import shutil
from pathlib import Path

from codefixer.adapters.sources.common import CliSourceBase, SourceCommandError, patch_hash
from codefixer.application.ports.sources import CandidateChange, SourcePolicy, WorkspaceManifest
from codefixer.infrastructure.process_runner import ProcessRunner


class GitSourceAdapter(CliSourceBase):
    source_type: str = "git"

    def __init__(self, repository_path: Path, command_prefix: list[str], runner: ProcessRunner | None = None):
        super().__init__(command_prefix, runner)
        self.repository_path = repository_path.resolve()

    def current_revision(self) -> str:
        revision = self._run(["rev-parse", "HEAD"], cwd=self.repository_path).stdout.strip()
        if not revision:
            raise SourceCommandError("git current revision is empty")
        return revision

    def refresh_and_current_revision(self) -> str:
        """Refresh origin before a BaselineCohort freezes one shared revision."""
        self._run(
            ["fetch", "--prune", "origin"],
            cwd=self.repository_path,
            timeout=600,
            env={"GIT_TERMINAL_PROMPT": "0"},
        )
        branch = self._run(
            ["symbolic-ref", "--quiet", "--short", "HEAD"],
            cwd=self.repository_path,
            allow_failure=True,
        ).stdout.strip()
        if branch:
            remote = self._run(
                ["rev-parse", "--verify", f"origin/{branch}"],
                cwd=self.repository_path,
                allow_failure=True,
            ).stdout.strip()
            if remote:
                return remote
            is_bare = self._run(
                ["rev-parse", "--is-bare-repository"],
                cwd=self.repository_path,
                allow_failure=True,
            ).stdout.strip()
            if is_bare == "true":
                mirror_revision = self._run(
                    ["rev-parse", "--verify", f"refs/heads/{branch}^{{commit}}"],
                    cwd=self.repository_path,
                    allow_failure=True,
                ).stdout.strip()
                if mirror_revision:
                    return mirror_revision
            raise SourceCommandError(f"git origin does not contain current branch: {branch}")
        remote_head = self._run(
            ["rev-parse", "--verify", "refs/remotes/origin/HEAD^{commit}"],
            cwd=self.repository_path,
            allow_failure=True,
        ).stdout.strip()
        if remote_head:
            return remote_head
        raise SourceCommandError("git origin has no resolvable authoritative branch")

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
        patch_file.write_bytes(candidate.patch_text.encode("utf-8"))
        try:
            # Git diff 来自规范化 index；在 Windows 上同时套用到 CRLF 工作区可能失败。
            # 先恢复规范 index，再由 Git 物化工作区，确保恢复后的 diff 与冻结版本一致。
            self._run(["apply", "--cached", "--binary", str(patch_file)], cwd=manifest.workspace_path)
            deleted_raw = self._run(
                ["diff", "--cached", "--name-only", "--diff-filter=D", "-z", manifest.base_revision, "--"],
                cwd=manifest.workspace_path,
            ).stdout
            workspace_root = manifest.workspace_path.resolve()
            for relative_path in (item for item in deleted_raw.split("\0") if item):
                target = (workspace_root / Path(relative_path)).resolve()
                try:
                    target.relative_to(workspace_root)
                except ValueError as exc:
                    raise SourceCommandError(
                        f"candidate deletion escapes workspace: {relative_path}"
                    ) from exc
                if target.is_file() or target.is_symlink():
                    target.unlink()
            self._run(["checkout-index", "--all", "--force"], cwd=manifest.workspace_path)
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
