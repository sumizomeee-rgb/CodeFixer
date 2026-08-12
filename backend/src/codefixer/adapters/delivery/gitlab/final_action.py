from __future__ import annotations

from pathlib import Path

from codefixer.adapters.delivery.gitlab.delivery import GitLabMrDelivery
from codefixer.application.ports.delivery import FinalActionResult, FrozenDeliveryContext


class GitLabMrFinalAction:
    action_type = "gitlabMr"

    def __init__(self, *, action_id: str, action_version: int, delivery: GitLabMrDelivery, project_id: str | int, config: dict[str, object], target_branches: tuple[str, ...], work_root: Path, title_template: str = "[CodeFixer] {task_id}", description_template: str = "Automated repair from CodeFixer run {run_id}.") -> None:
        self.action_id = action_id
        self.action_version = action_version
        self.delivery = delivery
        self.project_id = project_id
        self.config = config
        self.target_branches = target_branches
        self.work_root = work_root
        self.title_template = title_template
        self.description_template = description_template

    def execute(self, context: FrozenDeliveryContext) -> FinalActionResult:
        results = self.delivery.deliver(task_id=context.task_id, run_id=context.run_id, action_id=self.action_id, action_version=self.action_version, project_id=self.project_id, config=self.config, frozen_patch=context.patch_path, frozen_manifest=context.manifest_path, path_mappings=tuple((str(item.get("from", ".")), str(item.get("to", "."))) for item in self.config.get("pathMappings", []) if isinstance(item, dict)), base_revision=context.base_revision, target_branches=self.target_branches, work_root=self.work_root / context.run_id / self.action_id, title=self.title_template.format(task_id=context.task_id, run_id=context.run_id), description=self.description_template.format(task_id=context.task_id, run_id=context.run_id))
        detail: dict[str, object] = {"targets": [{"targetBranch": item.target_branch, "sourceBranch": item.source_branch, "mergeRequestIid": item.merge_request.iid, "webUrl": item.merge_request.web_url, "adoptedExisting": item.adopted_existing} for item in results]}
        if len(results) != len(self.target_branches):
            return FinalActionResult(self.action_id, self.action_type, "failed", "partial_success" if results else "failure", detail)
        return FinalActionResult(self.action_id, self.action_type, "succeeded", "success", detail)
