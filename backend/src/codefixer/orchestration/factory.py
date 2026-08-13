from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from codefixer.adapters.agents import build_agent_runtime
from codefixer.adapters.delivery.github import (
    GitHubCli,
    GitHubDeliveryMaterializer,
    GitHubPrDelivery,
    GitHubPrFinalAction,
)
from codefixer.adapters.delivery.gitlab import (
    GitDeliveryMaterializer,
    GitLabMrDelivery,
    GitLabMrFinalAction,
)
from codefixer.adapters.delivery_patch import FallbackPatchFinalAction, PatchFinalAction
from codefixer.adapters.sources.directory import DirectoryReadOnlySourceAdapter
from codefixer.adapters.sources.git import GitSourceAdapter
from codefixer.adapters.sources.svn import SvnSourceAdapter
from codefixer.adapters.tickets.factory import build_ticket_provider
from codefixer.application.ports.delivery import FinalAction, FrozenDeliveryContext
from codefixer.application.ports.sources import ModificationSourceAdapter, SourcePolicy
from codefixer.application.services.baseline_cohorts import BaselineCohortCoordinator, CohortSourceAdapter
from codefixer.application.services.delivery import DeliveryCoordinator
from codefixer.application.services.llm_slots import LeasedAgentRuntime, LlmSlotPool
from codefixer.application.services.preflight import run_project_preflight
from codefixer.application.services.stability import PreDeliveryStabilityGuard
from codefixer.application.services.verification import VerificationRunner, VerificationStep
from codefixer.application.services.workspace_detection import detect_workspace
from codefixer.config import LoadedConfig
from codefixer.infrastructure.artifact_index import ArtifactIndex
from codefixer.infrastructure.config_store import ConfigStore
from codefixer.infrastructure.delivery_store import DeliveryStore
from codefixer.infrastructure.leases import LeaseStore
from codefixer.infrastructure.task_store import TaskStore
from codefixer.orchestration.pipeline import ChangedPipeline, PipelineResult
from codefixer.protocols import ArtifactStore, SchemaRegistry


class ConfigurationNotReady(RuntimeError):
    def __init__(self, project_id: str, checks: list[dict[str, Any]]):
        super().__init__(f"project configuration is not ready: {project_id}")
        self.project_id = project_id
        self.checks = checks


class RunExecutor:
    def __init__(self, *, connection: sqlite3.Connection, config_store: ConfigStore, contracts_root: Path):
        self.connection = connection
        self.config_store = config_store
        self.contracts_root = contracts_root.resolve()

    def execute(self, run_id: str) -> PipelineResult:
        tasks = TaskStore(self.connection)
        summary = tasks.get_run_summary(run_id)
        loaded = self.config_store.reload()
        # SQLite connections are process-local; persistent LLM/cohort services use the
        # actual database opened by this executor, including isolated test deployments.
        database_row = self.connection.execute("PRAGMA database_list").fetchone()
        database_path = Path(str(database_row[2])).resolve() if database_row is not None else loaded.data_root / "codefixer.db"
        frozen_manifest = loaded.data_root / "tasks" / str(summary["task_id"]) / "runs" / run_id / "freeze-change" / "change-manifest.json"
        frozen_config = loaded.data_root / "tasks" / str(summary["task_id"]) / "runs" / run_id / "snapshot" / "config-snapshot.json"
        if frozen_manifest.is_file() and frozen_config.is_file():
            return self._resume_frozen_delivery(run_id, summary, loaded, frozen_manifest, frozen_config)

        project_id = str(summary["project_id"])
        project = next((dict(item) for item in loaded.config.projects if str(item.get("id")) == project_id), None)
        if project is None:
            return self._fail_before_execution(tasks, summary, run_id, code="project_not_found", summary_text=f"Project no longer exists: {project_id}", retryable=False)

        preflight = run_project_preflight(loaded, project)
        if not preflight["ready"]:
            return self._fail_before_execution(tasks, summary, run_id, code="configuration_not_ready", summary_text="Project preflight failed before execution", retryable=True, checks=preflight["checks"])
        try:
            return self._execute_fresh(run_id, tasks, loaded, project, summary, database_path)
        except (KeyError, ValueError, ConfigurationNotReady) as exc:
            return self._fail_before_execution(tasks, summary, run_id, code="configuration_not_ready", summary_text=str(exc), retryable=True, checks=preflight["checks"])

    def _execute_fresh(self, run_id: str, tasks: TaskStore, loaded: LoadedConfig, project: dict[str, Any], run_summary: dict[str, Any], database_path: Path) -> PipelineResult:
        project_id = str(project.get("id", ""))
        source_config = dict(project.get("modificationWorkspace") or {})
        repository_value = str(source_config.get("repositoryRoot") or source_config.get("path") or "")
        repository = Path(repository_value).resolve() if repository_value else None
        if repository is None or not repository.is_dir():
            raise ConfigurationNotReady(project_id, [])
        source_type = str(source_config.get("vcsKind"))
        executable_ref = "git-cli" if source_type == "git" else "svn-cli"
        source_command = self._command(loaded.config.executableBindings, executable_ref)
        if source_type == "git":
            raw_source: ModificationSourceAdapter = GitSourceAdapter(repository, source_command)
        elif source_type == "svn":
            raw_source = SvnSourceAdapter(repository, source_command, LeaseStore(self.connection))
        else:
            raise ConfigurationNotReady(project_id, [])
        cohort = BaselineCohortCoordinator(
            database_path,
            window_ms=loaded.config.execution.baselineCohortWindowMs,
        )
        source = CohortSourceAdapter(
            raw_source,
            cohort,
            repository_root=repository,
            baseline_identity=str(source_config.get("remoteUrl") or repository),
            baseline_resolver=(
                raw_source.refresh_and_current_revision
                if isinstance(raw_source, (GitSourceAdapter, SvnSourceAdapter))
                else raw_source.current_revision
            ),
            cancel_check=tasks.is_cancel_requested,
        )

        localization_config = dict(project.get("localizationSource") or {})
        localization_path_value = str(localization_config.get("path") or "")
        localization_path = Path(localization_path_value).resolve() if localization_path_value else None
        if localization_path is None or not localization_path.is_dir():
            raise ConfigurationNotReady(project_id, [])
        localization_detection = detect_workspace(str(localization_path))
        localization_repository_value = str(localization_detection.get("repositoryRoot") or localization_path)
        localization_repository = Path(localization_repository_value).resolve()
        if localization_detection.get("vcsKind") == "git":
            localization_source: ModificationSourceAdapter = GitSourceAdapter(localization_repository, self._command(loaded.config.executableBindings, "git-cli"))
        elif localization_detection.get("vcsKind") == "svn":
            localization_source = SvnSourceAdapter(localization_repository, self._command(loaded.config.executableBindings, "svn-cli"), LeaseStore(self.connection))
        else:
            localization_source = DirectoryReadOnlySourceAdapter(localization_path)

        provider_id = str(run_summary.get("provider_instance_id", ""))
        provider_config = next((dict(item) for item in loaded.config.ticketProviders if str(item.get("id")) == provider_id), None)
        if provider_config is None:
            raise ValueError(f"ticket provider no longer exists: {provider_id}")
        stability_guard = PreDeliveryStabilityGuard(build_ticket_provider(provider_config, self.config_store.get_secret), source)

        profiles = {str(item.get("id")): dict(item) for item in loaded.config.agentProfiles if item.get("id")}
        current_profile_id = loaded.config.execution.currentModelId.strip()
        current_profile = profiles.get(current_profile_id)
        if current_profile is None:
            raise ValueError(f"current model does not exist: {current_profile_id}")
        # Every LLM-consuming stage in a run uses the same globally selected model.
        # Build separate runtime objects so the stages remain independent sessions.
        pool = LlmSlotPool(database_path, capacity=loaded.config.execution.maxConcurrentLlmCalls)
        def leased_runtime() -> LeasedAgentRuntime:
            return LeasedAgentRuntime(build_agent_runtime(current_profile, loaded.config.executableBindings), pool, task_run_id=run_id)
        scope_discovery_agent = leased_runtime()
        discovery_agent = leased_runtime()
        repair_agent = leased_runtime()
        review_agent = leased_runtime()

        verification_config = project.get("verification") or {}
        default_timeout = int(verification_config.get("timeoutSeconds", 1200))
        verification_steps: list[VerificationStep] = []
        for raw in verification_config.get("steps") or []:
            executable = self._command(loaded.config.executableBindings, str(raw.get("executableRef", "")))
            args = raw.get("args") or []
            if not isinstance(args, list) or not all(isinstance(item, str) for item in args):
                raise ValueError("verification args must be string array")
            verification_steps.append(VerificationStep(id=str(raw.get("id", "step")), command=tuple([*executable, *args]), timeout_seconds=int(raw.get("timeoutSeconds", default_timeout)), required=bool(raw.get("required", True)), working_directory=str(raw.get("workingDirectory", "."))))

        actions = self._build_delivery_actions(loaded, project)
        delivery_store = DeliveryStore(self.connection)
        policy = SourcePolicy(
            allowed_roots=tuple(str(item) for item in source_config.get("allowedRoots") or (".",)),
            denied_roots=tuple(str(item) for item in source_config.get("deniedRoots") or ()),
            allowed_extensions=tuple(str(item) for item in source_config.get("allowedExtensions") or ()),
        )
        return ChangedPipeline(
            tasks=tasks,
            artifacts=ArtifactStore(loaded.data_root, SchemaRegistry(self.contracts_root)),
            artifact_index=ArtifactIndex(self.connection, loaded.data_root),
            source=source,
            localization_source=localization_source,
            scope_discovery_agent=scope_discovery_agent,
            discovery_agent=discovery_agent,
            repair_agent=repair_agent,
            review_agent=review_agent,
            verification_runner=VerificationRunner(),
            verification_steps=tuple(verification_steps),
            project=project,
            source_policy=policy,
            delivery=DeliveryCoordinator(
                tuple(actions),
                fallback_action=FallbackPatchFinalAction(store=delivery_store, data_root=loaded.data_root, project_id=project_id),
            ),
            max_repair_attempts=loaded.config.execution.maxRepairAttempts,
            stability_guard=stability_guard,
        ).run(run_id)

    @staticmethod
    def _fail_before_execution(tasks: TaskStore, run_summary: dict[str, Any], run_id: str, *, code: str, summary_text: str, retryable: bool, checks: object | None = None) -> PipelineResult:
        tasks.claim_run(run_id)
        failure: dict[str, object] = {"code": code, "stage": "prepare", "summary": summary_text, "retryable": retryable, "side_effects": []}
        if checks is not None:
            failure["checks"] = checks
        tasks.fail_run(run_id, failure)
        return PipelineResult(str(run_summary["task_id"]), run_id, "failed", None, ())

    def _resume_frozen_delivery(self, run_id: str, summary: dict[str, Any], loaded: LoadedConfig, manifest_path: Path, config_path: Path) -> PipelineResult:
        import json

        tasks = TaskStore(self.connection)
        tasks.claim_run(run_id)
        task_id = str(summary["task_id"])
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            config_snapshot = json.loads(config_path.read_text(encoding="utf-8"))
            project = config_snapshot.get("project")
            if not isinstance(project, dict):
                raise ValueError("frozen config snapshot has no project")
            SchemaRegistry(self.contracts_root).validate("change-manifest", manifest)
            patch_path = manifest_path.parent / str(manifest["diff"]["path"])
            actions = self._build_delivery_actions(loaded, project)
            stage_id = tasks.start_stage(run_id, "deliver", tasks.next_stage_attempt(run_id, "deliver"))
            coordinator = DeliveryCoordinator(
                tuple(actions),
                fallback_action=FallbackPatchFinalAction(store=DeliveryStore(self.connection), data_root=loaded.data_root, project_id=str(project.get("id", "project"))),
            )
            report = coordinator.execute_report(FrozenDeliveryContext(task_id=task_id, run_id=run_id, change_version=int(manifest["change_version"]), source_id=str(manifest["modification_source"]["id"]), base_revision=str(manifest["modification_source"]["base_revision"]), patch_path=patch_path, patch_sha256=str(manifest["diff"]["sha256"]), manifest_path=manifest_path))
            results = report.results
            if not report.succeeded:
                tasks.finish_stage(stage_id, status="failed", failure={"code": "delivery_failed"})
                failure = {"code": "delivery_failed", "stage": "deliver", "summary": "Recovered delivery still has failed required actions", "retryable": True, "side_effects": [result.detail for result in results if result.succeeded]}
                tasks.fail_run(run_id, failure)
                return PipelineResult(task_id, run_id, "failed", None, results)
            tasks.finish_stage(stage_id, status="completed")
            tasks.complete_run(run_id, "changed")
            return PipelineResult(task_id, run_id, "completed", "changed", results)
        except Exception as exc:
            failure = {"code": "delivery_recovery_failed", "stage": "deliver", "summary": str(exc), "retryable": True, "side_effects": []}
            tasks.fail_run(run_id, failure)
            return PipelineResult(task_id, run_id, "failed", None, ())

    def _build_delivery_actions(self, loaded: LoadedConfig, project: dict[str, Any]) -> list[FinalAction]:
        delivery_store = DeliveryStore(self.connection)
        actions: list[FinalAction] = []
        for raw_action in project.get("finalActions") or []:
            action = dict(raw_action)
            action_id = str(action.get("id", ""))
            if action.get("type") == "patch":
                output_value = str(action.get("outputDirectory") or "")
                output = Path(output_value).resolve() if output_value else None
                if output is None:
                    raise ValueError(f"Patch output directory missing for {action_id}")
                actions.append(PatchFinalAction(action_id=action_id, action_version=1, store=delivery_store, output_directory=output, filename_template=str(action.get("filenameTemplate", "{task_id}-{run_id}.patch")), overwrite=bool(action.get("overwrite", False))))
            elif action.get("type") == "gitlabMr":
                workspace = dict(project.get("modificationWorkspace") or {})
                materialization_value = str(workspace.get("repositoryRoot") or workspace.get("path") or "")
                materialization = Path(materialization_value).resolve() if materialization_value else None
                if materialization is None or not materialization.is_dir():
                    raise ValueError(f"GitLab repository missing for {action_id}")
                materializer = GitDeliveryMaterializer(materialization, self._command(loaded.config.executableBindings, "git-cli"))
                targets = tuple(str(item) for item in (action.get("targetBranches") or []))
                actions.append(GitLabMrFinalAction(action_id=action_id, action_version=1, delivery=GitLabMrDelivery(delivery_store, materializer), config=action, target_branches=targets, work_root=loaded.data_root / "delivery-work", title_template=str(action.get("titleTemplate", "[CodeFixer] {task_id}")), description_template=str(action.get("descriptionTemplate", "Automated repair from CodeFixer run {run_id}."))))
            elif action.get("type") == "githubPr":
                workspace = dict(project.get("modificationWorkspace") or {})
                materialization_value = str(workspace.get("repositoryRoot") or workspace.get("path") or "")
                materialization = Path(materialization_value).resolve() if materialization_value else None
                if materialization is None or not materialization.is_dir():
                    raise ValueError(f"GitHub repository missing for {action_id}")
                materializer = GitHubDeliveryMaterializer(materialization, self._command(loaded.config.executableBindings, "git-cli"))
                github = GitHubCli(materialization, self._command(loaded.config.executableBindings, "gh-cli"))
                targets = tuple(str(item) for item in (action.get("targetBranches") or []))
                actions.append(GitHubPrFinalAction(action_id=action_id, action_version=1, delivery=GitHubPrDelivery(delivery_store, materializer, github), config=action, target_branches=targets, work_root=loaded.data_root / "delivery-work", title_template=str(action.get("titleTemplate", "[CodeFixer] {task_id}")), description_template=str(action.get("descriptionTemplate", "Automated repair from CodeFixer run {run_id}."))))
        return actions

    @staticmethod
    def _command(bindings: dict[str, dict[str, Any]], binding_id: str) -> list[str]:
        binding = bindings.get(binding_id)
        command = binding.get("command") if isinstance(binding, dict) else None
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise ValueError(f"executable binding is invalid: {binding_id}")
        return list(command)
