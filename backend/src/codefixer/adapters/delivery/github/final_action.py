from __future__ import annotations

from pathlib import Path

from codefixer.adapters.delivery.github.delivery import GitHubPrDelivery
from codefixer.application.ports.delivery import FinalActionResult, FrozenDeliveryContext


class GitHubPrFinalAction:
    action_type = "githubPr"

    def __init__(
        self,
        *,
        action_id: str,
        action_version: int,
        delivery: GitHubPrDelivery,
        config: dict[str, object],
        target_branches: tuple[str, ...],
        work_root: Path,
        title_template: str = "[CodeFixer] {task_id}",
        description_template: str = "Automated repair from CodeFixer run {run_id}.",
    ) -> None:
        self.action_id = action_id
        self.action_version = action_version
        self.delivery = delivery
        self.config = config
        self.target_branches = target_branches
        self.work_root = work_root
        self.title_template = title_template
        self.description_template = description_template

    def execute(self, context: FrozenDeliveryContext) -> FinalActionResult:
        raw_path_mappings = self.config.get("pathMappings", [])
        path_mappings = raw_path_mappings if isinstance(raw_path_mappings, list) else []
        delivered = self.delivery.deliver(
            task_id=context.task_id,
            run_id=context.run_id,
            action_id=self.action_id,
            action_version=self.action_version,
            config=self.config,
            frozen_patch=context.patch_path,
            frozen_manifest=context.manifest_path,
            path_mappings=tuple(
                (str(item.get("from", ".")), str(item.get("to", ".")))
                for item in path_mappings
                if isinstance(item, dict)
            ),
            base_revision=context.base_revision,
            target_branches=self.target_branches,
            work_root=self.work_root / context.run_id / self.action_id,
            title=self.title_template.format(task_id=context.task_id, run_id=context.run_id),
            description=self.description_template.format(
                task_id=context.task_id, run_id=context.run_id
            ),
        )
        detail: dict[str, object] = {
            "deliveryCommit": delivered.delivery_commit,
            "targets": [
                {
                    "targetBranch": item.target_branch,
                    "sourceBranch": item.source_branch,
                    "pullRequestNumber": item.pull_request.number,
                    "webUrl": item.pull_request.web_url,
                    "state": item.pull_request.state,
                    "adoptedExisting": item.adopted_existing,
                }
                for item in delivered.targets
            ],
            "failures": [
                {
                    "targetBranch": item.target_branch,
                    "sourceBranch": item.source_branch,
                    "reason": item.reason,
                    "errorType": item.error_type,
                }
                for item in delivered.failures
            ],
        }
        return FinalActionResult(
            self.action_id,
            self.action_type,
            delivered.status,
            delivered.outcome,
            detail,
        )
