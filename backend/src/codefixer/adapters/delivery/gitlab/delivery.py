from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import httpx

from codefixer.adapters.delivery.gitlab.client import GitLabApiError, GitLabClient, MergeRequestRef
from codefixer.adapters.delivery.gitlab.materializer import GitDeliveryMaterializer, safe_branch_component
from codefixer.adapters.sources.common import SourceCommandError
from codefixer.infrastructure.config_store import canonical_json
from codefixer.infrastructure.delivery_store import DeliveryStore


@dataclass(frozen=True)
class GitLabTargetResult:
    target_branch: str
    source_branch: str
    merge_request: MergeRequestRef
    adopted_existing: bool


class GitLabMrDelivery:
    def __init__(self, store: DeliveryStore, client: GitLabClient, materializer: GitDeliveryMaterializer):
        self.store = store
        self.client = client
        self.materializer = materializer

    def deliver(self, *, task_id: str, run_id: str, action_id: str, action_version: int, project_id: str | int, config: dict[str, object], frozen_patch: Path, frozen_manifest: Path | None = None, path_mappings: tuple[tuple[str, str], ...] = (), base_revision: str, target_branches: tuple[str, ...], work_root: Path, title: str, description: str) -> tuple[GitLabTargetResult, ...]:
        config_hash = hashlib.sha256(canonical_json(config).encode()).hexdigest()
        intent_key = hashlib.sha256(f"{run_id}:{action_id}:{action_version}:{config_hash}".encode()).hexdigest()
        action = self.store.ensure_action(task_run_id=run_id, action_id=action_id, action_version=action_version, action_type="gitlabMr", config_hash=config_hash, intent_key=intent_key)
        action_id_db = int(action["id"])
        self.store.mark_action(action_id_db, status="running")
        self.materializer.refresh()
        previous_result = action.get("result") if isinstance(action.get("result"), dict) else {}
        previous_commit = str(previous_result.get("deliveryCommit", "")) if previous_result else ""
        if previous_commit and self.materializer.commit_exists(previous_commit):
            delivery_commit = previous_commit
        else:
            if path_mappings:
                if frozen_manifest is None:
                    raise ValueError("pathMappings require frozen manifest")
                if not target_branches:
                    raise ValueError("gitlabMr requires at least one target branch")
                delivery_commit = self.materializer.create_mapped_delivery_commit(base_ref=f"{self.materializer.remote}/{target_branches[0]}", frozen_manifest=frozen_manifest, path_mappings=path_mappings, worktree=work_root / "delivery-commit", message=f"CodeFixer {task_id} {run_id}")
            else:
                delivery_commit = self.materializer.create_delivery_commit(base_revision=base_revision, patch_path=frozen_patch, worktree=work_root / "delivery-commit", message=f"CodeFixer {task_id} {run_id}")
            self.store.mark_action(action_id_db, status="running", result={"deliveryCommit": delivery_commit})
        results: list[GitLabTargetResult] = []
        failed = False
        for target in target_branches:
            target_row = self.store.ensure_target(action_id_db, target)
            target_id = int(target_row["id"])
            source_branch = f"codefixer/{safe_branch_component(task_id)}/{safe_branch_component(run_id)}/{safe_branch_component(target)}"
            self.store.mark_target(target_id, status="reconciling", remote_ref=source_branch)
            try:
                existing = self.client.find_merge_request(project_id, source_branch, target)
                if existing is not None:
                    if existing.state not in {"opened", "merged"}:
                        self.store.mark_target(target_id, status="failed", outcome="failure", external_id=existing.iid, external_url=existing.web_url, result={"reason": f"existing_mr_{existing.state}"})
                        failed = True
                        continue
                    self.store.mark_target(target_id, status="succeeded", outcome="success", external_id=existing.iid, external_url=existing.web_url, result={"adoptedExisting": True})
                    results.append(GitLabTargetResult(target, source_branch, existing, True))
                    continue
                self.store.mark_target(target_id, status="running", remote_ref=source_branch)
                remote_commit = self.client.get_branch_commit(project_id, source_branch)
                if remote_commit is None:
                    materialized = self.materializer.materialize_target(delivery_commit=delivery_commit, target_branch=target, source_branch=source_branch, worktree=work_root / f"target-{safe_branch_component(target)}")
                    remote_commit = materialized.target_commit
                    self.store.mark_target(target_id, status="reconciling", remote_ref=source_branch, result={"targetCommit": remote_commit, "deliveryCommit": delivery_commit})
                existing = self.client.find_merge_request(project_id, source_branch, target)
                if existing is None:
                    existing = self.client.create_merge_request(project_id, source_branch=source_branch, target_branch=target, title=title, description=description)
                self.store.mark_target(target_id, status="succeeded", outcome="success", external_id=existing.iid, external_url=existing.web_url, result={"adoptedExisting": False})
                results.append(GitLabTargetResult(target, source_branch, existing, False))
            except (GitLabApiError, SourceCommandError, httpx.HTTPError, ValueError) as exc:
                failed = True
                self.store.mark_target(target_id, status="failed", outcome="failure", remote_ref=source_branch, result={"reason": str(exc), "errorType": type(exc).__name__})
        if failed:
            self.store.mark_action(action_id_db, status="failed", outcome="partial_success" if results else "failure", result={"deliveryCommit": delivery_commit})
        else:
            self.store.mark_action(action_id_db, status="succeeded", outcome="success", result={"deliveryCommit": delivery_commit})
        return tuple(results)
