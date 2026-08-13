from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from codefixer.adapters.delivery.github.client import PullRequestRef
from codefixer.adapters.delivery.gitlab.materializer import safe_branch_component
from codefixer.adapters.sources.common import SourceCommandError
from codefixer.infrastructure.config_store import canonical_json
from codefixer.infrastructure.delivery_store import DeliveryStore


class GitHubClient(Protocol):
    def list_pull_requests(
        self, *, source_branch: str, target_branch: str
    ) -> tuple[PullRequestRef, ...]: ...

    def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> PullRequestRef: ...


class GitHubMaterializer(Protocol):
    remote: str

    def refresh(self) -> None: ...

    def commit_exists(self, commit: str) -> bool: ...

    def create_delivery_commit(
        self, *, base_revision: str, patch_path: Path, worktree: Path, message: str
    ) -> str: ...

    def create_mapped_delivery_commit(
        self,
        *,
        base_ref: str,
        frozen_manifest: Path,
        path_mappings: tuple[tuple[str, str], ...],
        worktree: Path,
        message: str,
    ) -> str: ...

    def create_target_commit(
        self, *, delivery_commit: str, target_branch: str, worktree: Path
    ) -> str: ...

    def remote_branch_commit(self, branch: str) -> str | None: ...

    def push_target(self, *, target_commit: str, source_branch: str) -> None: ...


@dataclass(frozen=True)
class GitHubTargetResult:
    target_branch: str
    source_branch: str
    pull_request: PullRequestRef
    adopted_existing: bool


@dataclass(frozen=True)
class GitHubTargetFailure:
    target_branch: str
    source_branch: str
    reason: str
    error_type: str


@dataclass(frozen=True)
class GitHubDeliveryResult:
    delivery_commit: str
    targets: tuple[GitHubTargetResult, ...]
    failures: tuple[GitHubTargetFailure, ...]

    @property
    def status(self) -> str:
        return "failed" if self.failures else "succeeded"

    @property
    def outcome(self) -> str:
        if not self.failures:
            return "success"
        return "partial_success" if self.targets else "failure"


class GitHubPrDelivery:
    def __init__(
        self,
        store: DeliveryStore,
        materializer: GitHubMaterializer,
        github: GitHubClient,
    ) -> None:
        self.store = store
        self.materializer = materializer
        self.github = github

    def deliver(
        self,
        *,
        task_id: str,
        run_id: str,
        action_id: str,
        action_version: int,
        config: dict[str, object],
        frozen_patch: Path,
        frozen_manifest: Path | None = None,
        path_mappings: tuple[tuple[str, str], ...] = (),
        base_revision: str,
        target_branches: tuple[str, ...],
        work_root: Path,
        title: str,
        description: str,
    ) -> GitHubDeliveryResult:
        if not target_branches:
            raise ValueError("githubPr requires at least one target branch")
        config_hash = hashlib.sha256(canonical_json(config).encode()).hexdigest()
        intent_key = hashlib.sha256(
            f"{run_id}:{action_id}:{action_version}:{config_hash}".encode()
        ).hexdigest()
        action = self.store.ensure_action(
            task_run_id=run_id,
            action_id=action_id,
            action_version=action_version,
            action_type="githubPr",
            config_hash=config_hash,
            intent_key=intent_key,
        )
        action_db_id = int(action["id"])
        raw_previous_result = action.get("result")
        previous_result: dict[str, object] = (
            raw_previous_result if isinstance(raw_previous_result, dict) else {}
        )
        previous_commit = str(previous_result.get("deliveryCommit", ""))
        self.store.mark_action(action_db_id, status="running")
        try:
            self.materializer.refresh()
            if previous_commit and self.materializer.commit_exists(previous_commit):
                delivery_commit = previous_commit
            else:
                if path_mappings:
                    if frozen_manifest is None:
                        raise ValueError("pathMappings require frozen manifest")
                    delivery_commit = self.materializer.create_mapped_delivery_commit(
                        base_ref=f"{self.materializer.remote}/{target_branches[0]}",
                        frozen_manifest=frozen_manifest,
                        path_mappings=path_mappings,
                        worktree=work_root / "delivery-commit",
                        message=f"CodeFixer {task_id} {run_id}",
                    )
                else:
                    delivery_commit = self.materializer.create_delivery_commit(
                        base_revision=base_revision,
                        patch_path=frozen_patch,
                        worktree=work_root / "delivery-commit",
                        message=f"CodeFixer {task_id} {run_id}",
                    )
                self.store.mark_action(
                    action_db_id, status="running", result={"deliveryCommit": delivery_commit}
                )
        except (SourceCommandError, ValueError) as exc:
            failure = GitHubTargetFailure(
                target_branch="__action__",
                source_branch="",
                reason=str(exc),
                error_type=type(exc).__name__,
            )
            self.store.mark_action(
                action_db_id,
                status="failed",
                outcome="failure",
                result={
                    **({"deliveryCommit": previous_commit} if previous_commit else {}),
                    "reason": failure.reason,
                    "errorType": failure.error_type,
                },
            )
            return GitHubDeliveryResult(previous_commit, (), (failure,))

        results: list[GitHubTargetResult] = []
        failures: list[GitHubTargetFailure] = []
        for target in target_branches:
            source_branch = (
                f"codefixer/{safe_branch_component(task_id)}/"
                f"{safe_branch_component(run_id)}/{safe_branch_component(target)}"
            )
            target_row = self.store.ensure_target(action_db_id, target)
            target_id = int(target_row["id"])
            target_commit = ""
            try:
                persisted = target_row.get("result")
                persisted_result = persisted if isinstance(persisted, dict) else {}
                if target_row.get("status") == "succeeded" and target_row.get("external_url"):
                    pull_request = PullRequestRef(
                        number=str(target_row.get("external_id") or ""),
                        web_url=str(target_row["external_url"]),
                        state="open",
                        source_branch=source_branch,
                        target_branch=target,
                    )
                    results.append(GitHubTargetResult(target, source_branch, pull_request, True))
                    continue

                self.store.mark_target(
                    target_id, status="reconciling", remote_ref=source_branch
                )
                matches = self.github.list_pull_requests(
                    source_branch=source_branch, target_branch=target
                )
                if len(matches) > 1:
                    raise SourceCommandError(
                        f"multiple GitHub PRs match delivery branch {source_branch}"
                    )
                if len(matches) == 1:
                    pull_request = matches[0]
                    self.store.mark_target(
                        target_id,
                        status="succeeded",
                        outcome="success",
                        remote_ref=source_branch,
                        external_id=pull_request.number,
                        external_url=pull_request.web_url,
                        result={"adoptedExisting": True},
                    )
                    results.append(GitHubTargetResult(target, source_branch, pull_request, True))
                    continue

                expected_commit = str(persisted_result.get("expectedCommit", ""))
                remote_commit = self.materializer.remote_branch_commit(source_branch)
                if remote_commit is not None:
                    if not expected_commit or remote_commit != expected_commit:
                        raise SourceCommandError(
                            "delivery branch exists without a matching persisted GitHub intent: "
                            f"{source_branch}"
                        )
                    target_commit = expected_commit
                else:
                    if expected_commit and self.materializer.commit_exists(expected_commit):
                        target_commit = expected_commit
                    else:
                        target_commit = self.materializer.create_target_commit(
                            delivery_commit=delivery_commit,
                            target_branch=target,
                            worktree=work_root / f"target-{safe_branch_component(target)}",
                        )
                    self.store.mark_target(
                        target_id,
                        status="reconciling",
                        remote_ref=source_branch,
                        result={"expectedCommit": target_commit, "branchPushed": False},
                    )
                    self.materializer.push_target(
                        target_commit=target_commit, source_branch=source_branch
                    )
                    self.store.mark_target(
                        target_id,
                        status="reconciling",
                        remote_ref=source_branch,
                        result={"expectedCommit": target_commit, "branchPushed": True},
                    )

                pull_request = self.github.create_pull_request(
                    source_branch=source_branch,
                    target_branch=target,
                    title=title,
                    description=description,
                )
                self.store.mark_target(
                    target_id,
                    status="succeeded",
                    outcome="success",
                    remote_ref=source_branch,
                    external_id=pull_request.number,
                    external_url=pull_request.web_url,
                    result={
                        "adoptedExisting": False,
                        "expectedCommit": target_commit,
                        "branchPushed": True,
                    },
                )
                results.append(GitHubTargetResult(target, source_branch, pull_request, False))
            except (SourceCommandError, ValueError) as exc:
                failure = GitHubTargetFailure(
                    target_branch=target,
                    source_branch=source_branch,
                    reason=str(exc),
                    error_type=type(exc).__name__,
                )
                failures.append(failure)
                self.store.mark_target(
                    target_id,
                    status="failed",
                    outcome="failure",
                    remote_ref=source_branch,
                    result={
                        "reason": failure.reason,
                        "errorType": failure.error_type,
                        **({"expectedCommit": target_commit} if target_commit else {}),
                    },
                )

        outcome = "partial_success" if results and failures else "failure" if failures else "success"
        status = "failed" if failures else "succeeded"
        self.store.mark_action(
            action_db_id,
            status=status,
            outcome=outcome,
            result={
                "deliveryCommit": delivery_commit,
                "targetCount": len(target_branches),
                "succeededTargetCount": len(results),
                "failedTargetCount": len(failures),
            },
        )
        return GitHubDeliveryResult(delivery_commit, tuple(results), tuple(failures))
