from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from codefixer.adapters.agents import build_agent_runtime
from codefixer.adapters.delivery.gitlab import (
    GitDeliveryMaterializer,
    GitLabClient,
    GitLabMrDelivery,
    GitLabMrFinalAction,
)
from codefixer.adapters.delivery_patch import PatchFinalAction
from codefixer.adapters.sources.git import GitSourceAdapter
from codefixer.adapters.sources.svn import SvnSourceAdapter
from codefixer.adapters.tickets.factory import build_ticket_provider
from codefixer.application.ports.delivery import FinalAction, FrozenDeliveryContext
from codefixer.application.ports.sources import SourcePolicy
from codefixer.application.services.delivery import DeliveryCoordinator
from codefixer.application.services.preflight import resolve_path_binding, run_project_preflight
from codefixer.application.services.stability import PreDeliveryStabilityGuard
from codefixer.application.services.verification import VerificationRunner, VerificationStep
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
            return self._execute_fresh(run_id, tasks, loaded, project, summary)
        except (KeyError, ValueError, ConfigurationNotReady) as exc:
            return self._fail_before_execution(tasks, summary, run_id, code="configuration_not_ready", summary_text=str(exc), retryable=True, checks=preflight["checks"])

    def _execute_fresh(self, run_id: str, tasks: TaskStore, loaded: LoadedConfig, project: dict[str, Any], run_summary: dict[str, Any]) -> PipelineResult:
        project_id = str(project.get("id", ""))
        source_config = dict(project.get("modificationSource") or {})
        repository_ref = str(source_config.get("repositoryRef", ""))
        repository = resolve_path_binding(loaded, repository_ref)
        if repository is None:
            raise ConfigurationNotReady(project_id, [])
        executable_ref = str(source_config.get("executableRef") or ("git-cli" if source_config.get("type") == "git" else "svn-cli"))
        source_command = self._command(loaded.config.executableBindings, executable_ref)
        source_type = str(source_config.get("type"))
        if source_type == "git":
            source = GitSourceAdapter(repository, source_command)
        elif source_type == "svn":
            source = SvnSourceAdapter(repository, source_command, LeaseStore(self.connection))
        else:
            raise ConfigurationNotReady(project_id, [])

        provider_id = str(run_summary.get("provider_instance_id", ""))
        provider_config = next((dict(item) for item in loaded.config.ticketProviders if str(item.get("id")) == provider_id), None)
        if provider_config is None:
            raise ValueError(f"ticket provider no longer exists: {provider_id}")
        stability_guard = PreDeliveryStabilityGuard(build_ticket_provider(provider_config, self.config_store.get_secret), source)

        profiles = {str(item.get("id")): dict(item) for item in loaded.config.agentProfiles if item.get("id")}
        agent_ids = project.get("agents") or {}
        scope_discovery_agent = build_agent_runtime(profiles[str(agent_ids["scopeDiscovery"])], loaded.config.executableBindings)
        discovery_agent = build_agent_runtime(profiles[str(agent_ids["discovery"])], loaded.config.executableBindings)
        repair_agent = build_agent_runtime(profiles[str(agent_ids["repair"])], loaded.config.executableBindings)
        review_agent = build_agent_runtime(profiles[str(agent_ids["review"])], loaded.config.executableBindings)

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
            scope_discovery_agent=scope_discovery_agent,
            discovery_agent=discovery_agent,
            repair_agent=repair_agent,
            review_agent=review_agent,
            verification_runner=VerificationRunner(),
            verification_steps=tuple(verification_steps),
            project=project,
            source_policy=policy,
            delivery=DeliveryCoordinator(tuple(actions)),
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
            results = DeliveryCoordinator(tuple(actions)).execute(FrozenDeliveryContext(task_id=task_id, run_id=run_id, change_version=int(manifest["change_version"]), source_id=str(manifest["modification_source"]["id"]), base_revision=str(manifest["modification_source"]["base_revision"]), patch_path=patch_path, patch_sha256=str(manifest["diff"]["sha256"]), manifest_path=manifest_path))
            if any(not result.succeeded for result in results):
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
                output = resolve_path_binding(loaded, str(action.get("outputDirectoryRef", "")))
                if output is None:
                    raise ValueError(f"Patch output binding missing for {action_id}")
                actions.append(PatchFinalAction(action_id=action_id, action_version=1, store=delivery_store, output_directory=output, filename_template=str(action.get("filenameTemplate", "{task_id}-{run_id}.patch")), overwrite=bool(action.get("overwrite", False))))
            elif action.get("type") == "gitlabMr":
                connection_config = self._connection(loaded.config.connections, str(action.get("connectionRef", "")))
                token_ref = str(connection_config.get("tokenSecretRef", ""))
                token = self.config_store.get_secret(token_ref) if token_ref else None
                if not token:
                    raise ValueError(f"GitLab token secret missing: {token_ref}")
                materialization = resolve_path_binding(loaded, str(action.get("materializationRepositoryRef", "")))
                if materialization is None:
                    raise ValueError(f"GitLab materialization repository missing for {action_id}")
                materializer = GitDeliveryMaterializer(materialization, self._command(loaded.config.executableBindings, str(action.get("gitExecutableRef", "git-cli"))))
                gitlab = GitLabClient(str(connection_config.get("baseUrl", "")), token)
                targets = tuple(str(item) for item in (action.get("targetBranches") or []))
                actions.append(GitLabMrFinalAction(action_id=action_id, action_version=1, delivery=GitLabMrDelivery(delivery_store, gitlab, materializer), project_id=str(action.get("projectPath", "")), config=action, target_branches=targets, work_root=loaded.data_root / "delivery-work", title_template=str(action.get("titleTemplate", "[CodeFixer] {task_id}")), description_template=str(action.get("descriptionTemplate", "Automated repair from CodeFixer run {run_id}."))))
        return actions

    @staticmethod
    def _command(bindings: dict[str, dict[str, Any]], binding_id: str) -> list[str]:
        binding = bindings.get(binding_id)
        command = binding.get("command") if isinstance(binding, dict) else None
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise ValueError(f"executable binding is invalid: {binding_id}")
        return list(command)

    @staticmethod
    def _connection(connections: list[dict[str, Any]], connection_id: str) -> dict[str, Any]:
        for item in connections:
            if str(item.get("id")) == connection_id:
                return dict(item)
        raise ValueError(f"connection not found: {connection_id}")
