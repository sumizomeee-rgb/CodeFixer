from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from codefixer.application.ports.agents import AgentRequest, AgentRuntime
from codefixer.application.ports.delivery import FinalActionResult, FrozenDeliveryContext
from codefixer.application.ports.sources import ModificationSourceAdapter, SourcePolicy, WorkspaceManifest
from codefixer.application.services.delivery import DeliveryCoordinator
from codefixer.application.services.freeze import freeze_change
from codefixer.application.services.stability import PreDeliveryStabilityGuard
from codefixer.application.services.verification import VerificationRunner, VerificationStep
from codefixer.infrastructure.artifact_index import ArtifactIndex
from codefixer.infrastructure.config_store import canonical_json
from codefixer.infrastructure.task_store import TaskStore
from codefixer.protocols import ArtifactProtocolError, ArtifactStore, StageEntry, StoredArtifact, render_stage_entry

@dataclass(frozen=True)
class PipelineResult:
    task_id: str
    run_id: str
    status: str
    result: str | None
    deliveries: tuple[FinalActionResult, ...] = ()

class PipelineFailure(RuntimeError):

    def __init__(self, code: str, stage: str, summary: str):
        super().__init__(summary)
        self.failure = {'code': code, 'stage': stage, 'summary': summary, 'retryable': False, 'side_effects': []}

class PipelineCanceled(RuntimeError):
    pass

class ChangedPipeline:
    """First executable CodeFixer journey: located -> repair -> verify -> review -> freeze -> patch."""

    def __init__(self, *, tasks: TaskStore, artifacts: ArtifactStore, artifact_index: ArtifactIndex, source: ModificationSourceAdapter, discovery_agent: AgentRuntime, repair_agent: AgentRuntime, review_agent: AgentRuntime, verification_runner: VerificationRunner, verification_steps: tuple[VerificationStep, ...], project: dict[str, Any], source_policy: SourcePolicy, delivery: DeliveryCoordinator, max_repair_attempts: int=3, stability_guard: PreDeliveryStabilityGuard | None=None) -> None:
        self.tasks = tasks
        self.artifacts = artifacts
        self.artifact_index = artifact_index
        self.source = source
        self.discovery_agent = discovery_agent
        self.repair_agent = repair_agent
        self.review_agent = review_agent
        self.verification_runner = verification_runner
        self.verification_steps = verification_steps
        self.project = project
        self.source_policy = source_policy
        self.delivery = delivery
        self.max_repair_attempts = max_repair_attempts
        self.stability_guard = stability_guard

    def run(self, run_id: str) -> PipelineResult:
        context = self.tasks.claim_run(run_id)
        task_id = str(context['task_id'])
        self._check_cancel(run_id)
        discovery_manifest: WorkspaceManifest | None = None
        repair_manifest: WorkspaceManifest | None = None
        try:
            project_json = canonical_json(self.project)
            project_hash = hashlib.sha256(project_json.encode()).hexdigest()
            input_fingerprint = hashlib.sha256(f"{context['ticket_content_hash']}:{project_hash}".encode()).hexdigest()
            self.tasks.freeze_run_inputs(run_id, project_config_hash=project_hash, input_fingerprint=input_fingerprint)
            prepare_stage = self.tasks.start_stage(run_id, 'prepare', 1)
            discovery_workspace = self.artifacts.run_root(task_id, run_id) / 'workspaces/discovery'
            discovery_manifest = self.source.prepare(source_id=str(self.project['modificationSource'].get('id', 'project-source')), run_id=f'{run_id}:discovery', workspace_path=discovery_workspace)
            snapshot = self._write_snapshot(task_id, run_id, context, discovery_manifest, project_hash)
            self.tasks.finish_stage(prepare_stage, status='completed', output_path=str(self.artifacts.run_root(task_id, run_id) / 'snapshot'))
            discovery = self._run_agent_stage(task_id=task_id, run_id=run_id, stage='discovery', attempt=None, agent=self.discovery_agent, access='read_only', cwd=discovery_manifest.workspace_path, inputs=(('Frozen ticket', snapshot['ticket']), ('Project policy', snapshot['project']), ('Source manifest', snapshot['source'])), schema_name='task-discovery', output_name='task-discovery.json')
            discovery_payload = json.loads(discovery.path.read_text(encoding='utf-8'))
            if discovery_payload['source']['id'] != discovery_manifest.source_id:
                raise PipelineFailure('source_mismatch', 'discovery', 'Discovery reported a different modification source')
            if discovery_payload['source']['revision'] != discovery_manifest.base_revision:
                raise PipelineFailure('source_mismatch', 'discovery', 'Discovery reported a different frozen revision')
            decision = discovery_payload['decision']
            if decision == 'unresolved':
                raise PipelineFailure('discovery_no_target', 'discovery', 'Discovery could not locate a repair target')
            if decision == 'no_change_claim':
                no_change = self._run_agent_stage(task_id=task_id, run_id=run_id, stage='no_change_verify', attempt=None, agent=self.repair_agent, access='read_only', cwd=discovery_manifest.workspace_path, inputs=(('Frozen ticket', snapshot['ticket']), ('Discovery result', discovery.path), ('Source manifest', snapshot['source'])), schema_name='no-change-report', output_name='no-change-report.json')
                no_change_payload = json.loads(no_change.path.read_text(encoding='utf-8'))
                source_claim = no_change_payload.get('source', {})
                if source_claim.get('id') != discovery_manifest.source_id or source_claim.get('revision') != discovery_manifest.base_revision:
                    raise PipelineFailure('source_mismatch', 'no_change_verify', 'No-change report is not bound to the frozen source')
                no_change_review = self._run_agent_stage(task_id=task_id, run_id=run_id, stage='review', attempt=1, agent=self.review_agent, access='read_only', cwd=discovery_manifest.workspace_path, inputs=(('Frozen ticket', snapshot['ticket']), ('Discovery result', discovery.path), ('No-change report', no_change.path)), schema_name='review', output_name='review.json')
                no_change_review_payload = json.loads(no_change_review.path.read_text(encoding='utf-8'))
                if no_change_review_payload['mode'] != 'no_change' or no_change_review_payload['input_sha256'] != no_change.sha256 or no_change_review_payload['verdict'] != 'approved':
                    raise PipelineFailure('insufficient_evidence', 'review', 'Independent review did not approve the no-change evidence')
                self._check_cancel(run_id)
                self._run_stability_check(run_id=run_id, context=context, frozen_source_revision=discovery_manifest.base_revision)
                self.tasks.complete_run(run_id, 'no_change')
                return PipelineResult(task_id, run_id, 'completed', 'no_change', ())
            base_revision = discovery_manifest.base_revision
            self.source.cleanup(discovery_manifest)
            discovery_manifest = None
            self._check_cancel(run_id)
            repair_workspace = self.artifacts.run_root(task_id, run_id) / 'workspaces/repair'
            repair_manifest = self.source.prepare(source_id=str(self.project['modificationSource'].get('id', 'project-source')), run_id=f'{run_id}:repair', workspace_path=repair_workspace, base_revision=base_revision)
            last_review: StoredArtifact | None = None
            verification_artifact: StoredArtifact | None = None
            candidate = None
            for attempt in range(1, self.max_repair_attempts + 1):
                repair_inputs: list[tuple[str, Path]] = [('Frozen ticket', snapshot['ticket']), ('Discovery result', discovery.path), ('Project policy', snapshot['project']), ('Workspace manifest', snapshot['source'])]
                if last_review is not None:
                    repair_inputs.append(('Previous review feedback', last_review.path))
                self._run_agent_stage(task_id=task_id, run_id=run_id, stage='repair', attempt=attempt, agent=self.repair_agent, access='workspace_write', cwd=repair_manifest.workspace_path, inputs=tuple(repair_inputs), schema_name='repair-result', output_name='repair-result.json')
                candidate = self.source.collect_change(repair_manifest, self.source_policy)
                if candidate.unauthorized_paths:
                    raise PipelineFailure('unauthorized_change', 'repair', 'Repair changed unauthorized paths: ' + ', '.join(candidate.unauthorized_paths))
                if not candidate.changed_paths or not candidate.patch_text:
                    raise PipelineFailure('repair_no_valid_diff', 'repair', 'Repair produced no valid diff')
                candidate_artifact = self.artifacts.write_text(self.artifacts.stage_root(task_id, run_id, 'verify', attempt) / 'candidate.patch', candidate.patch_text)
                self._index(run_id, 'verify', 'candidate_patch', candidate_artifact, attempt)
                verify_stage = self.tasks.start_stage(run_id, 'verify', attempt)
                verification_payload = self.verification_runner.run(candidate.patch_sha256, self.verification_steps, default_cwd=repair_manifest.workspace_path, cancel_check=lambda: self.tasks.is_cancel_requested(run_id))
                verification_view = self.source.collect_change(repair_manifest, self.source_policy)
                verification_mutated = verification_view.patch_sha256 != candidate.patch_sha256 or verification_view.changed_paths != candidate.changed_paths or verification_view.operations != candidate.operations
                if verification_mutated:
                    try:
                        self.source.restore_candidate(repair_manifest, candidate)
                        restored = self.source.collect_change(repair_manifest, self.source_policy)
                    except Exception as exc:
                        self.tasks.finish_stage(verify_stage, status='failed', failure={'code': 'verification_mutated_workspace', 'summary': str(exc)})
                        raise PipelineFailure('verification_mutated_workspace', 'verify', 'Verification changed the repair workspace and the candidate could not be restored') from exc
                    if restored.patch_sha256 != candidate.patch_sha256 or restored.changed_paths != candidate.changed_paths or restored.operations != candidate.operations:
                        self.tasks.finish_stage(verify_stage, status='failed', failure={'code': 'verification_mutated_workspace'})
                        raise PipelineFailure('verification_mutated_workspace', 'verify', 'Verification side effects could not be scrubbed back to the frozen candidate')
                verification_artifact = self.artifacts.write_json(self.artifacts.stage_root(task_id, run_id, 'verify', attempt) / 'verification.json', verification_payload, schema_name='verification', copy_schema=True)
                self._index(run_id, 'verify', 'verification', verification_artifact, attempt)
                if any((bool(step.get('canceled')) for step in verification_payload.get('steps', []))):
                    self.tasks.finish_stage(verify_stage, status='canceled')
                    raise PipelineCanceled()
                self.tasks.finish_stage(verify_stage, status='completed' if bool(verification_payload['passed']) else 'failed', output_path=str(verification_artifact.path), failure=None if bool(verification_payload['passed']) else {'code': 'verification_failed'})
                if not bool(verification_payload['passed']):
                    if attempt >= self.max_repair_attempts:
                        raise PipelineFailure('verification_failed', 'verify', 'Required verification did not pass')
                    continue
                last_review = self._run_agent_stage(task_id=task_id, run_id=run_id, stage='review', attempt=attempt, agent=self.review_agent, access='read_only', cwd=repair_manifest.workspace_path, inputs=(('Frozen ticket', snapshot['ticket']), ('Discovery result', discovery.path), ('Candidate diff', candidate_artifact.path), ('Verification result', verification_artifact.path)), schema_name='review', output_name='review.json')
                review_payload = json.loads(last_review.path.read_text(encoding='utf-8'))
                if review_payload['mode'] != 'change' or review_payload['input_sha256'] != candidate.patch_sha256:
                    raise PipelineFailure('agent_protocol_invalid', 'review', 'Review did not bind to the actual candidate diff')
                verdict = review_payload['verdict']
                if verdict == 'approved':
                    break
                if verdict == 'rejected':
                    raise PipelineFailure('review_rejected', 'review', str(review_payload['summary']))
                if attempt >= self.max_repair_attempts:
                    raise PipelineFailure('repair_cycle_exhausted', 'review', 'Repair/review cycle exhausted')
            if candidate is None or last_review is None or verification_artifact is None:
                raise PipelineFailure('repair_cycle_exhausted', 'review', 'Repair did not reach an approved candidate')
            self._check_cancel(run_id)
            self._run_stability_check(run_id=run_id, context=context, frozen_source_revision=repair_manifest.base_revision)
            freeze_stage = self.tasks.start_stage(run_id, 'freeze_change', 1)
            patch_artifact, manifest_artifact = freeze_change(artifacts=self.artifacts, task_id=task_id, run_id=run_id, manifest=repair_manifest, candidate=candidate, verification=verification_artifact, review=last_review, config_sha256=project_hash)
            self._index(run_id, 'freeze_change', 'frozen_patch', patch_artifact)
            self._index(run_id, 'freeze_change', 'change_manifest', manifest_artifact)
            self.tasks.finish_stage(freeze_stage, status='completed', output_path=str(manifest_artifact.path))
            self._check_cancel(run_id)
            deliver_stage = self.tasks.start_stage(run_id, 'deliver', 1)
            try:
                deliveries = self.delivery.execute(FrozenDeliveryContext(task_id=task_id, run_id=run_id, change_version=1, source_id=repair_manifest.source_id, base_revision=repair_manifest.base_revision, patch_path=patch_artifact.path, patch_sha256=patch_artifact.sha256, manifest_path=manifest_artifact.path))
            except Exception as exc:
                failure = {'code': 'delivery_exception', 'stage': 'deliver', 'summary': str(exc), 'retryable': True, 'side_effects': []}
                self.tasks.finish_stage(deliver_stage, status='failed', failure=failure)
                self.tasks.fail_run(run_id, failure)
                return PipelineResult(task_id, run_id, 'failed', None, ())
            failed_deliveries = [item for item in deliveries if not item.succeeded]
            if failed_deliveries:
                succeeded = [item for item in deliveries if item.succeeded]
                summary = 'Final action failed after partial delivery' if succeeded else 'Final actions failed'
                self.tasks.finish_stage(deliver_stage, status='failed', failure={'code': 'delivery_failed', 'summary': summary})
                raise PipelineFailure('delivery_failed', 'deliver', summary)
            self.tasks.finish_stage(deliver_stage, status='completed')
            self.tasks.complete_run(run_id, 'changed')
            return PipelineResult(task_id, run_id, 'completed', 'changed', deliveries)
        except PipelineCanceled:
            self.tasks.cancel_run(run_id)
            return PipelineResult(task_id, run_id, 'canceled', None, ())
        except (PipelineFailure, ArtifactProtocolError) as exc:
            failure = exc.failure if isinstance(exc, PipelineFailure) else {'code': 'agent_protocol_invalid', 'stage': 'protocol', 'summary': str(exc), 'retryable': False, 'side_effects': []}
            self.tasks.fail_run(run_id, failure)
            return PipelineResult(task_id, run_id, 'failed', None, ())
        finally:
            if discovery_manifest is not None:
                self.source.cleanup(discovery_manifest)
            if repair_manifest is not None:
                self.source.cleanup(repair_manifest)

    def _write_snapshot(self, task_id: str, run_id: str, context: dict[str, Any], source: WorkspaceManifest, project_hash: str) -> dict[str, Path]:
        root = self.artifacts.run_root(task_id, run_id) / 'snapshot'
        ticket_json = self.artifacts.write_json(root / 'ticket.raw.json', context['ticket_payload'])
        ticket_md = self.artifacts.write_text(root / 'ticket.md', f"# {context['title']}\n\nProvider: {context['provider_instance_id']}\nTicket: {context['external_ticket_id']}\n\nRaw snapshot: `{ticket_json.path.resolve()}`\n")
        project = self.artifacts.write_text(root / 'project-policy.md', '# Frozen Project Policy\n\n```json\n' + json.dumps(self.project, ensure_ascii=False, indent=2) + '\n```\n')
        source_artifact = self.artifacts.write_json(root / 'source-manifest.json', {'schema_version': 1, 'id': source.source_id, 'type': source.source_type, 'revision': source.base_revision, 'workspace': str(source.workspace_path.resolve())})
        config = self.artifacts.write_json(root / 'config-snapshot.json', {'schema_version': 1, 'project_sha256': project_hash, 'project': self.project})
        for kind, item in (('ticket', ticket_json), ('ticket', ticket_md), ('project_policy', project), ('source_manifest', source_artifact), ('config_snapshot', config)):
            self._index(run_id, 'prepare', kind, item)
        return {'ticket': ticket_md.path, 'project': project.path, 'source': source_artifact.path, 'config': config.path}

    def _run_agent_stage(self, *, task_id: str, run_id: str, stage: str, attempt: int | None, agent: AgentRuntime, access: str, cwd: Path, inputs: tuple[tuple[str, Path], ...], schema_name: str, output_name: str) -> StoredArtifact:
        stage_attempt = attempt or 1
        stage_db_id = self.tasks.start_stage(run_id, stage, stage_attempt)
        stage_root = self.artifacts.stage_root(task_id, run_id, stage, attempt)
        output_path = stage_root / output_name
        schema_path = self.artifacts.schema_registry.schema_path(schema_name)
        entry_artifact = self.artifacts.write_text(stage_root / 'entry.md', render_stage_entry(StageEntry(task_id=task_id, run_id=run_id, stage=stage, attempt=attempt, inputs=inputs, output_path=output_path, schema_path=schema_path)))
        self._index(run_id, stage, 'entry', entry_artifact, attempt)
        result = agent.run(AgentRequest(stage='review' if stage == 'review' else 'repair' if stage == 'repair' else 'no_change_verify' if stage == 'no_change_verify' else 'discovery', entry_file=entry_artifact.path, cwd=cwd, access='workspace_write' if access == 'workspace_write' else 'read_only', output_schema=schema_path, cancel_check=lambda: self.tasks.is_cancel_requested(run_id)))
        if result.status == 'canceled':
            self.tasks.finish_stage(stage_db_id, status='canceled')
            raise PipelineCanceled()
        if result.status == 'timed_out':
            self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': 'agent_timeout'})
            raise PipelineFailure('agent_timeout', stage, f'{stage} Agent timed out')
        if result.status != 'succeeded':
            self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': 'agent_failed'})
            raise PipelineFailure('agent_protocol_invalid', stage, f'{stage} Agent did not complete successfully')
        if self.tasks.is_cancel_requested(run_id):
            self.tasks.finish_stage(stage_db_id, status='canceled')
            raise PipelineCanceled()
        if output_path.is_file():
            payload = json.loads(output_path.read_text(encoding='utf-8'))
        elif isinstance(result.structured_output, dict):
            payload = result.structured_output
        else:
            self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': 'agent_protocol_invalid'})
            raise PipelineFailure('agent_protocol_invalid', stage, f'{stage} Agent produced no structured result')
        artifact = self.artifacts.write_json(output_path, payload, schema_name=schema_name, copy_schema=True)
        self._index(run_id, stage, schema_name, artifact, attempt)
        self.tasks.finish_stage(stage_db_id, status='completed', output_path=str(artifact.path))
        return artifact

    def _run_stability_check(self, *, run_id: str, context: dict[str, Any], frozen_source_revision: str) -> None:
        if self.stability_guard is None:
            return
        attempt = self.tasks.next_stage_attempt(run_id, 'pre_delivery_check')
        stage_id = self.tasks.start_stage(run_id, 'pre_delivery_check', attempt)
        stability = self.stability_guard.check(external_ticket_id=str(context['external_ticket_id']), frozen_external_version=str(context['external_version']) if context.get('external_version') is not None else None, frozen_ticket_content_hash=str(context['ticket_content_hash']), frozen_source_revision=frozen_source_revision)
        if not stability.ready:
            self.tasks.finish_stage(stage_id, status='failed', failure={'code': stability.code, 'summary': stability.summary, 'detail': stability.detail})
            raise PipelineFailure(stability.code or 'pre_delivery_check_failed', 'pre_delivery_check', stability.summary)
        self.tasks.finish_stage(stage_id, status='completed')

    def _check_cancel(self, run_id: str) -> None:
        if self.tasks.is_cancel_requested(run_id):
            raise PipelineCanceled()

    def _index(self, run_id: str, stage: str, kind: str, artifact: StoredArtifact, attempt: int | None=None) -> None:
        self.artifact_index.register(task_run_id=run_id, stage_id=stage, artifact_type=kind, artifact=artifact, attempt=attempt)
