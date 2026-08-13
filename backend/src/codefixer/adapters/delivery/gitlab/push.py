from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import quote

from codefixer.adapters.delivery.gitlab.materializer import GitDeliveryMaterializer, safe_branch_component
from codefixer.adapters.sources.common import SourceCommandError
from codefixer.application.ports.delivery import FinalActionResult, FrozenDeliveryContext
from codefixer.infrastructure.config_store import canonical_json
from codefixer.infrastructure.delivery_store import DeliveryStore


def _project_path(remote_url: str) -> str:
    value = remote_url.strip().removesuffix(".git")
    scp = re.fullmatch(r"[^@]+@[^:]+:(.+)", value)
    if scp:
        return scp.group(1).strip("/")
    ssh = re.fullmatch(r"ssh://(?:[^@]+@)?[^/]+/(.+)", value)
    if ssh:
        return ssh.group(1).strip("/")
    match = re.match(r"https?://[^/]+/(.+)", value)
    if match:
        return match.group(1).strip("/")
    raise ValueError("无法从 origin 解析 GitLab 项目路径")


class GitLabPushFinalAction:
    action_type = "gitlabPush"

    def __init__(
        self,
        *,
        action_id: str,
        action_version: int,
        store: DeliveryStore,
        materializer: GitDeliveryMaterializer,
        config: dict[str, object],
        work_root: Path,
        web_base_url: str,
    ) -> None:
        self.action_id = action_id
        self.action_version = action_version
        self.store = store
        self.materializer = materializer
        self.config = config
        self.work_root = work_root
        self.web_base_url = web_base_url.rstrip("/")

    def execute(self, context: FrozenDeliveryContext) -> FinalActionResult:
        config_hash = hashlib.sha256(canonical_json(self.config).encode()).hexdigest()
        intent_key = hashlib.sha256(
            f"{context.run_id}:{self.action_id}:{self.action_version}:{config_hash}".encode()
        ).hexdigest()
        action = self.store.ensure_action(
            task_run_id=context.run_id,
            action_id=self.action_id,
            action_version=self.action_version,
            action_type=self.action_type,
            config_hash=config_hash,
            intent_key=intent_key,
        )
        action_db_id = int(action["id"])
        self.store.mark_action(action_db_id, status="running")
        previous = action.get("result") if isinstance(action.get("result"), dict) else {}
        try:
            self.materializer.refresh()
            delivery_commit = str(previous.get("commitSha") or "")
            if not delivery_commit or not self.materializer.commit_exists(delivery_commit):
                delivery_commit = self.materializer.create_delivery_commit(
                    base_revision=context.base_revision,
                    patch_path=context.patch_path,
                    worktree=self.work_root / context.run_id / self.action_id / "delivery-commit",
                    message=context.commit_subject,
                )
            branch = f"codefixer/{safe_branch_component(context.ticket_key)}/{safe_branch_component(context.run_id)[:12]}"
            remote_commit = self.materializer.remote_branch_commit(branch)
            adopted = remote_commit == delivery_commit
            if remote_commit is not None and not adopted:
                raise SourceCommandError(f"远端任务分支已存在且内容不同：{branch}")
            if remote_commit is None:
                self.materializer.push_commit(delivery_commit, branch)
                confirmed = self.materializer.remote_branch_commit(branch)
                if confirmed != delivery_commit:
                    raise SourceCommandError("推送后无法确认远端 Commit SHA")
            remote_url = self.materializer.remote_url()
            project_path = _project_path(remote_url)
            project_url = f"{self.web_base_url}/{project_path}"
            detail: dict[str, object] = {
                "commitSha": delivery_commit,
                "commitSubject": context.commit_subject,
                "commitUrl": f"{project_url}/-/commit/{delivery_commit}",
                "remoteBranch": branch,
                "branchUrl": f"{project_url}/-/tree/{quote(branch, safe='')}",
                "adoptedExisting": adopted,
                "nextStep": "在 GitLab Web 打开该 Commit，选择目标分支并 Cherry-pick。",
            }
            self.store.mark_action(action_db_id, status="succeeded", outcome="success", result=detail)
            return FinalActionResult(self.action_id, self.action_type, "succeeded", "success", detail)
        except Exception as exc:
            detail = {"code": "gitlab_push_failed", "error": str(exc), "errorType": type(exc).__name__}
            self.store.mark_action(action_db_id, status="failed", outcome="failure", result=detail)
            return FinalActionResult(self.action_id, self.action_type, "failed", "failure", detail)
