from __future__ import annotations

from pathlib import Path

from codefixer.adapters.delivery.gitlab.materializer import GitDeliveryMaterializer
from codefixer.adapters.sources.common import SourceCommandError


class GitHubDeliveryMaterializer(GitDeliveryMaterializer):
    """把冻结修改物化到 origin 分支；PR 本身由 GitHubCli 创建。"""

    def create_target_commit(
        self,
        *,
        delivery_commit: str,
        target_branch: str,
        worktree: Path,
    ) -> str:
        if worktree.exists():
            raise SourceCommandError(f"materialization worktree exists: {worktree}")
        remote_target = f"{self.remote}/{target_branch}"
        self._run(["rev-parse", "--verify", remote_target], cwd=self.repository)
        worktree.parent.mkdir(parents=True, exist_ok=True)
        self._run(["worktree", "add", "--detach", str(worktree), remote_target], cwd=self.repository)
        try:
            self._run(
                ["-c", "user.name=CodeFixer", "-c", "user.email=codefixer@local", "cherry-pick", delivery_commit],
                cwd=worktree,
            )
            commit = self._run(["rev-parse", "HEAD"], cwd=worktree).stdout.strip()
            if not commit:
                raise SourceCommandError("GitHub delivery target commit is empty")
            return commit
        finally:
            self._run(
                ["worktree", "remove", "--force", str(worktree)],
                cwd=self.repository,
                allow_failure=True,
            )

    def push_target(self, *, target_commit: str, source_branch: str) -> None:
        self._run(
            ["push", self.remote, f"{target_commit}:refs/heads/{source_branch}"],
            cwd=self.repository,
            timeout=600,
        )
