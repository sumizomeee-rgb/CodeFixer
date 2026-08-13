from __future__ import annotations

import re
from pathlib import Path

from codefixer.adapters.sources.common import CliSourceBase, SourceCommandError
from codefixer.infrastructure.process_runner import ProcessRunner


def safe_branch_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return cleaned[:80] or "target"


class GitDeliveryMaterializer(CliSourceBase):
    def __init__(self, repository: Path, command_prefix: list[str], runner: ProcessRunner | None = None, remote: str = "origin"):
        super().__init__(command_prefix, runner)
        self.repository = repository.resolve()
        self.remote = remote

    def refresh(self) -> None:
        self._run(["fetch", "--prune", self.remote], cwd=self.repository, timeout=600)

    def remote_url(self) -> str:
        value = self._run(["remote", "get-url", self.remote], cwd=self.repository).stdout.strip()
        if not value:
            raise SourceCommandError(f"Git remote has no URL: {self.remote}")
        return value

    def remote_branch_commit(self, branch: str) -> str | None:
        result = self._run(
            ["ls-remote", "--heads", self.remote, f"refs/heads/{branch}"],
            cwd=self.repository,
            allow_failure=True,
            timeout=60,
        )
        if result.exit_code != 0 or not result.stdout.strip():
            return None
        return result.stdout.split()[0]

    def push_commit(self, commit: str, branch: str) -> None:
        self._run(
            ["push", self.remote, f"{commit}:refs/heads/{branch}"],
            cwd=self.repository,
            timeout=600,
        )

    def commit_exists(self, commit: str) -> bool:
        result = self._run(["cat-file", "-e", f"{commit}^{{commit}}"], cwd=self.repository, allow_failure=True)
        return result.exit_code == 0

    def create_delivery_commit(self, *, base_revision: str, patch_path: Path, worktree: Path, message: str) -> str:
        if worktree.exists():
            raise SourceCommandError(f"materialization worktree exists: {worktree}")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        self._run(["worktree", "add", "--detach", str(worktree), base_revision], cwd=self.repository)
        try:
            self._run(["apply", "--index", "--binary", str(patch_path.resolve())], cwd=worktree)
            self._run(["-c", "user.name=CodeFixer", "-c", "user.email=codefixer@local", "commit", "-m", message], cwd=worktree)
            commit = self._run(["rev-parse", "HEAD"], cwd=worktree).stdout.strip()
            if not commit:
                raise SourceCommandError("delivery commit is empty")
            return commit
        finally:
            self._run(["worktree", "remove", "--force", str(worktree)], cwd=self.repository, allow_failure=True)
