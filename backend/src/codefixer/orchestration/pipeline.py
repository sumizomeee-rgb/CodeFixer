from __future__ import annotations
import hashlib
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from codefixer.application.ports.agents import AgentRequest, AgentRuntime
from codefixer.application.ports.delivery import FinalActionResult, FrozenDeliveryContext
from codefixer.application.ports.sources import ModificationSourceAdapter, SourcePolicy, WorkspaceManifest
from codefixer.application.ports.tickets import TicketProvider
from codefixer.application.services.delivery import DeliveryCoordinator
from codefixer.application.services.delivery_metadata import build_delivery_metadata
from codefixer.application.services.freeze import freeze_change
from codefixer.application.services.similar_reports import SimilarReportFinder
from codefixer.application.services.stability import PreDeliveryStabilityGuard
from codefixer.application.services.verification import VerificationRunner, VerificationStep
from codefixer.infrastructure.artifact_index import ArtifactIndex
from codefixer.infrastructure.config_store import canonical_json
from codefixer.infrastructure.task_store import TaskStore
from codefixer.protocols import ArtifactProtocolError, ArtifactStore, StageEntry, StoredArtifact, render_stage_entry

_HTML_TAG = re.compile(r"<[^>]+>")

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
    """One localization Agent followed by one isolated coding Agent."""

    def __init__(self, *, tasks: TaskStore, artifacts: ArtifactStore, artifact_index: ArtifactIndex, source: ModificationSourceAdapter, localization_source: ModificationSourceAdapter | None=None, discovery_agent: AgentRuntime, repair_agent: AgentRuntime, verification_runner: VerificationRunner, verification_steps: tuple[VerificationStep, ...], project: dict[str, Any], source_policy: SourcePolicy, delivery: DeliveryCoordinator, ticket_provider: TicketProvider | None=None, stability_guard: PreDeliveryStabilityGuard | None=None) -> None:
        self.tasks = tasks
        self.artifacts = artifacts
        self.artifact_index = artifact_index
        self.source = source
        self.localization_source = localization_source or source
        self.discovery_agent = discovery_agent
        self.repair_agent = repair_agent
        self.verification_runner = verification_runner
        self.verification_steps = verification_steps
        self.project = project
        self.source_policy = source_policy
        self.delivery = delivery
        self.ticket_provider = ticket_provider
        self.stability_guard = stability_guard

    def run(self, run_id: str) -> PipelineResult:
        context = self.tasks.claim_run(run_id)
        task_id = str(context['task_id'])
        self._check_cancel(run_id)
        discovery_manifest: WorkspaceManifest | None = None
        repair_manifest: WorkspaceManifest | None = None
        repair_payload: dict[str, Any] = {}
        try:
            project_json = canonical_json(self.project)
            project_hash = hashlib.sha256(project_json.encode()).hexdigest()
            input_fingerprint = hashlib.sha256(f"{context['ticket_content_hash']}:{project_hash}".encode()).hexdigest()
            self.tasks.freeze_run_inputs(run_id, project_config_hash=project_hash, input_fingerprint=input_fingerprint)
            prepare_stage = self.tasks.start_stage(run_id, 'prepare', 1)
            localization_config = self.project.get('localizationSource') or {}
            localization_id = str(localization_config.get('id', 'localization-source'))
            modification_config = self.project.get('modificationWorkspace') or {}
            modification_id = str(modification_config.get('id', 'modification-workspace'))
            discovery_manifest = self.localization_source.prepare(
                source_id=localization_id,
                run_id=f'{run_id}:discovery',
                workspace_path=self.artifacts.run_root(task_id, run_id) / 'workspaces/discovery',
            )
            snapshot = self._write_snapshot(task_id, run_id, context, discovery_manifest, project_hash)
            self.tasks.finish_stage(prepare_stage, status='completed', output_path=str(self.artifacts.run_root(task_id, run_id) / 'snapshot'))
            discovery_inputs = [('Complete ticket context', snapshot['ticket']), ('Project policy', snapshot['project']), ('Localization source manifest', snapshot['source'])]
            discovery_notes = [
                'Investigate the ticket against the configured localization directory and return a complete Markdown localization report.',
                'You may use the full shell for read-only investigation, including svn info/log/cat. Never update, revert, commit, or write inside the localization directory.',
                'The complete ticket context lists frozen image and attachment paths. Open and inspect any relevant available media when the runtime supports vision; report unavailable media as a limitation.',
                'Include the ticket interpretation, likely root cause, relevant files and symbols, evidence, suggested coding direction, and remaining uncertainty.',
                str(self.project.get('localizationPrompt') or '').strip(),
            ]
            similar = SimilarReportFinder(self.tasks.connection, self.artifact_index.data_root).find(
                current_run_id=run_id,
                current_task_id=task_id,
                project_id=str(context['project_id']),
                title=str(context['title']),
                localization_source_id=discovery_manifest.source_id,
                localization_workspace=discovery_manifest.workspace_path,
            )
            if similar is not None:
                discovery_inputs.append(('Similar historical localization report', similar.path))
                similarity_basis = f"共同功能模块“{similar.matched_feature}”" if similar.matched_feature else '标题内容相似'
                discovery_notes.append(
                    f'Historical reference: ticket {similar.external_ticket_id} ({similar.title}), selected because of {similarity_basis}; similarity score {similar.score:.2f}. '
                    'It may help identify directories, module boundaries, and symbols, but it is not evidence for the current ticket. Re-check every claim against the current ticket and localization source.'
                )
            discovery = self._run_markdown_agent_stage(
                task_id=task_id,
                run_id=run_id,
                agent=self.discovery_agent,
                cwd=discovery_manifest.workspace_path,
                inputs=tuple(discovery_inputs),
                notes=tuple(discovery_notes),
            )
            self._check_cancel(run_id)
            workspace_stage = self.tasks.start_stage(run_id, 'workspace_prepare', 1)
            repair_workspace = self.artifacts.run_root(task_id, run_id) / 'workspaces/repair'
            try:
                repair_manifest = self.source.prepare(source_id=modification_id, run_id=f'{run_id}:repair', workspace_path=repair_workspace)
            except Exception as exc:
                self.tasks.finish_stage(workspace_stage, status='failed', failure={'code': 'workspace_prepare_failed', 'summary': str(exc)})
                raise
            repair_source = self.artifacts.write_json(
                self.artifacts.stage_root(task_id, run_id, 'workspace_prepare') / 'source-manifest.json',
                {
                    'schema_version': 1,
                    'id': repair_manifest.source_id,
                    'type': repair_manifest.source_type,
                    'revision': repair_manifest.base_revision,
                    'workspace': str(repair_manifest.workspace_path.resolve()),
                    'baseline_cohort_id': repair_manifest.baseline_cohort_id,
                },
            )
            self._index(run_id, 'workspace_prepare', 'source_manifest', repair_source)
            self.tasks.finish_stage(workspace_stage, status='completed', output_path=str(repair_source.path))
            repair_result = self._run_agent_stage(
                task_id=task_id,
                run_id=run_id,
                stage='repair',
                attempt=1,
                agent=self.repair_agent,
                access='workspace_write',
                cwd=repair_manifest.workspace_path,
                inputs=(('Complete ticket context', snapshot['ticket']), ('Localization report', discovery.path), ('Project policy', snapshot['project']), ('Workspace manifest', repair_source.path)),
                schema_name='repair-result',
                output_name='repair-result.json',
                notes=('Treat the localization report as navigation and analysis, not unquestionable fact. Re-check the current modification workspace before editing.',),
            )
            repair_payload = json.loads(repair_result.path.read_text(encoding='utf-8'))
            if repair_payload.get('outcome') == 'blocked':
                blocking_code = str(repair_payload.get('blocking_code') or 'unsupported_artifact_change')
                raise PipelineFailure(blocking_code, 'repair', str(repair_payload.get('summary') or 'Coding is blocked by a non-code boundary'))
            candidate = self.source.collect_change(repair_manifest, self.source_policy)
            if repair_payload.get('outcome') == 'no_valid_diff' and not candidate.changed_paths:
                self._run_stability_check(run_id=run_id, context=context, frozen_source_revision=repair_manifest.base_revision)
                self._write_conclusion(task_id, run_id, {'schema_version': 1, 'outcome': 'no_change', 'headline': '当前代码无需修改', 'cause': 'Coding Agent 核对修改工程后未发现需要生成的差异。', 'resolution': str(repair_payload.get('summary') or '未生成代码差异。')})
                self.tasks.complete_run(run_id, 'no_change')
                return PipelineResult(task_id, run_id, 'completed', 'no_change', ())
            if candidate.unauthorized_paths:
                raise PipelineFailure('unauthorized_change', 'repair', 'Coding changed unauthorized paths: ' + ', '.join(candidate.unauthorized_paths))
            if not candidate.changed_paths or not candidate.patch_text:
                raise PipelineFailure('repair_no_valid_diff', 'repair', 'Coding Agent claimed a change but produced no valid diff')
            candidate_artifact = self.artifacts.write_text(self.artifacts.stage_root(task_id, run_id, 'verify', 1) / 'candidate.patch', candidate.patch_text)
            self._index(run_id, 'verify', 'candidate_patch', candidate_artifact, 1)
            verify_stage = self.tasks.start_stage(run_id, 'verify', 1)
            verification_payload = self.verification_runner.run(candidate.patch_sha256, self.verification_steps, default_cwd=repair_manifest.workspace_path, cancel_check=lambda: self.tasks.is_cancel_requested(run_id))
            verification_view = self.source.collect_change(repair_manifest, self.source_policy)
            verification_mutated = (
                verification_view.patch_sha256 != candidate.patch_sha256
                or verification_view.changed_paths != candidate.changed_paths
                or verification_view.operations != candidate.operations
            )
            if verification_mutated:
                try:
                    self.source.restore_candidate(repair_manifest, candidate)
                    restored = self.source.collect_change(repair_manifest, self.source_policy)
                except Exception as exc:
                    self.tasks.finish_stage(verify_stage, status='failed', failure={'code': 'verification_mutated_workspace', 'summary': str(exc)})
                    raise PipelineFailure('verification_mutated_workspace', 'verify', 'Verification changed the coding workspace and the candidate could not be restored') from exc
                if (
                    restored.patch_sha256 != candidate.patch_sha256
                    or restored.changed_paths != candidate.changed_paths
                    or restored.operations != candidate.operations
                ):
                    self.tasks.finish_stage(verify_stage, status='failed', failure={'code': 'verification_mutated_workspace'})
                    raise PipelineFailure('verification_mutated_workspace', 'verify', 'Verification side effects could not be scrubbed back to the coding candidate')
            verification_artifact = self.artifacts.write_json(self.artifacts.stage_root(task_id, run_id, 'verify', 1) / 'verification.json', verification_payload, schema_name='verification', copy_schema=True)
            self._index(run_id, 'verify', 'verification', verification_artifact, 1)
            raw_steps = verification_payload.get('steps')
            if isinstance(raw_steps, list) and any(isinstance(item, dict) and bool(item.get('canceled')) for item in raw_steps):
                self.tasks.finish_stage(verify_stage, status='canceled')
                raise PipelineCanceled()
            self.tasks.finish_stage(verify_stage, status='completed' if bool(verification_payload['passed']) else 'failed', output_path=str(verification_artifact.path), failure=None if bool(verification_payload['passed']) else {'code': 'verification_failed'})
            if not bool(verification_payload['passed']):
                raise PipelineFailure('verification_failed', 'verify', 'Required verification did not pass')
            self._check_cancel(run_id)
            self._run_stability_check(run_id=run_id, context=context, frozen_source_revision=repair_manifest.base_revision)
            freeze_stage = self.tasks.start_stage(run_id, 'freeze_change', 1)
            delivery_metadata_payload = build_delivery_metadata(context=context, project=self.project, repair=repair_payload)
            delivery_metadata = self.artifacts.write_json(
                self.artifacts.run_root(task_id, run_id) / 'freeze-change' / 'delivery-metadata.json',
                delivery_metadata_payload,
                schema_name='delivery-metadata',
                copy_schema=True,
            )
            self._index(run_id, 'freeze_change', 'delivery_metadata', delivery_metadata)
            patch_artifact, manifest_artifact = freeze_change(artifacts=self.artifacts, task_id=task_id, run_id=run_id, manifest=repair_manifest, candidate=candidate, verification=verification_artifact, coding_result=repair_result, config_sha256=project_hash)
            self._index(run_id, 'freeze_change', 'frozen_patch', patch_artifact)
            self._index(run_id, 'freeze_change', 'change_manifest', manifest_artifact)
            self.tasks.finish_stage(freeze_stage, status='completed', output_path=str(manifest_artifact.path))
            self._write_conclusion(
                task_id,
                run_id,
                {
                    'schema_version': 1,
                    'outcome': 'changed',
                    'headline': f"已修复{delivery_metadata_payload['change_summary']}",
                    'cause': '定位 Agent 已生成定位报告，Coding Agent 已在当前修改基线上完成核对与修改。',
                    'resolution': str(repair_payload.get('summary') or delivery_metadata_payload['change_summary']),
                },
            )
            self._check_cancel(run_id)
            deliver_stage = self.tasks.start_stage(run_id, 'deliver', 1)
            try:
                delivery_report = self.delivery.execute_report(FrozenDeliveryContext(task_id=task_id, run_id=run_id, change_version=1, source_id=repair_manifest.source_id, base_revision=repair_manifest.base_revision, patch_path=patch_artifact.path, patch_sha256=patch_artifact.sha256, manifest_path=manifest_artifact.path, delivery_metadata_path=delivery_metadata.path, commit_subject=str(delivery_metadata_payload['commit_subject']), patch_filename=str(delivery_metadata_payload['patch_filename']), ticket_key=str(delivery_metadata_payload['ticket_key'])))
                deliveries = delivery_report.results
            except Exception as exc:
                failure = {'code': 'delivery_exception', 'stage': 'deliver', 'summary': str(exc), 'retryable': True, 'side_effects': []}
                self.tasks.finish_stage(deliver_stage, status='failed', failure=failure)
                self.tasks.fail_run(run_id, failure)
                return PipelineResult(task_id, run_id, 'failed', None, ())
            if not delivery_report.succeeded:
                succeeded = [item for item in delivery_report.required_results if item.succeeded]
                summary = 'Final action failed; a fallback Patch is available' if delivery_report.fallback_available else 'Final action failed after partial delivery' if succeeded else 'Final actions failed'
                self.tasks.finish_stage(deliver_stage, status='failed', failure={'code': 'delivery_failed', 'summary': summary})
                failure = {'code': 'fallback_patch_failed' if delivery_report.fallback_failed else 'delivery_failed', 'stage': 'deliver', 'summary': summary, 'retryable': True, 'side_effects': [item.detail for item in deliveries if item.succeeded]}
                self.tasks.fail_run(run_id, failure)
                return PipelineResult(task_id, run_id, 'failed', None, deliveries)
            self.tasks.finish_stage(deliver_stage, status='completed')
            self.tasks.complete_run(run_id, 'changed')
            return PipelineResult(task_id, run_id, 'completed', 'changed', deliveries)
        except PipelineCanceled:
            self._write_conclusion_safe(task_id, run_id, 'canceled', '任务已取消', '任务在完成前收到取消请求。', '未继续执行后续修改或交付。')
            self.tasks.cancel_run(run_id)
            return PipelineResult(task_id, run_id, 'canceled', None, ())
        except (PipelineFailure, ArtifactProtocolError) as exc:
            failure = exc.failure if isinstance(exc, PipelineFailure) else {'code': 'agent_protocol_invalid', 'stage': 'protocol', 'summary': str(exc), 'retryable': False, 'side_effects': []}
            self._write_conclusion_safe(task_id, run_id, 'failed', '任务未能完成', str(failure.get('summary') or '任务执行失败。'), '请按失败建议补充信息、修正配置或重新运行。')
            self.tasks.fail_run(run_id, failure)
            return PipelineResult(task_id, run_id, 'failed', None, ())
        finally:
            if discovery_manifest is not None:
                self.localization_source.cleanup(discovery_manifest)
            if repair_manifest is not None:
                self.source.cleanup(repair_manifest)

    def _write_snapshot(self, task_id: str, run_id: str, context: dict[str, Any], source: WorkspaceManifest, project_hash: str) -> dict[str, Path]:
        root = self.artifacts.run_root(task_id, run_id) / 'snapshot'
        ticket_payload = dict(context['ticket_payload'])
        media = self.ticket_provider.freeze_media(ticket_payload, root / 'media') if self.ticket_provider is not None else []
        ticket_payload['frozenMedia'] = media
        ticket_json = self.artifacts.write_json(root / 'ticket.raw.json', ticket_payload)
        description = html.unescape(_HTML_TAG.sub('', str(ticket_payload.get('description') or ''))).strip()
        comments = ticket_payload.get('comments')
        comment_lines = []
        if isinstance(comments, list):
            for item in comments:
                if isinstance(item, dict):
                    value = html.unescape(_HTML_TAG.sub('', str(item.get('description') or item.get('notes') or ''))).strip()
                    if value:
                        comment_lines.append(f"- {value}")
        media_lines = [
            f"- {item.get('label')}: `{item.get('path')}` ({item.get('contentType')})"
            if item.get('status') == 'ready'
            else f"- {item.get('label')}: 下载失败 — {item.get('reason')}"
            for item in media
        ]
        ticket_text = f"""# {context['title']}

## 工单

- 反馈源：{context['provider_instance_id']}
- 工单：{context['external_ticket_id']}
- 链接：{ticket_payload.get('url') or ''}
- 状态：{ticket_payload.get('status') or ''}
- 严重度：{ticket_payload.get('severity') or ''}
- 优先级：{ticket_payload.get('priority') or ''}
- 版本：{ticket_payload.get('requirementVersion') or ticket_payload.get('versionReport') or ''}

## 正文

{description or '（无正文）'}

## 评论

{chr(10).join(comment_lines) or '（无评论）'}

## 冻结媒体

{chr(10).join(media_lines) or '（无可用媒体）'}

## 完整原始数据

`{ticket_json.path.resolve()}`
"""
        ticket_md = self.artifacts.write_text(root / 'ticket.md', ticket_text)
        project = self.artifacts.write_text(root / 'project-policy.md', '# Frozen Project Policy\n\n```json\n' + json.dumps(self.project, ensure_ascii=False, indent=2) + '\n```\n')
        source_artifact = self.artifacts.write_json(root / 'source-manifest.json', {'schema_version': 1, 'id': source.source_id, 'type': source.source_type, 'revision': source.base_revision, 'workspace': str(source.workspace_path.resolve())})
        config = self.artifacts.write_json(root / 'config-snapshot.json', {'schema_version': 1, 'project_sha256': project_hash, 'project': self.project})
        for kind, item in (('ticket', ticket_json), ('ticket', ticket_md), ('project_policy', project), ('source_manifest', source_artifact), ('config_snapshot', config)):
            self._index(run_id, 'prepare', kind, item)
        return {'ticket': ticket_md.path, 'project': project.path, 'source': source_artifact.path, 'config': config.path}

    def _write_conclusion(self, task_id: str, run_id: str, payload: dict[str, Any]) -> StoredArtifact:
        normalized = dict(payload)
        limits = {'headline': 120, 'cause': 500, 'resolution': 500}
        fallbacks = {
            'headline': '任务处理结束',
            'cause': '平台已保留本次处理记录。',
            'resolution': '请查看任务阶段与交付结果。',
        }
        for field, maximum in limits.items():
            value = ' '.join(str(normalized.get(field) or fallbacks[field]).split())
            normalized[field] = value[:maximum]
        artifact = self.artifacts.write_json(
            self.artifacts.run_root(task_id, run_id) / 'final' / 'task-conclusion.json',
            normalized,
            schema_name='task-conclusion',
            copy_schema=True,
        )
        self._index(run_id, 'finalize', 'task_conclusion', artifact)
        return artifact

    def _write_conclusion_safe(self, task_id: str, run_id: str, outcome: str, headline: str, cause: str, resolution: str) -> None:
        try:
            self._write_conclusion(task_id, run_id, {'schema_version': 1, 'outcome': outcome, 'headline': headline, 'cause': cause[:500], 'resolution': resolution[:500]})
        except Exception:
            pass

    def _run_agent_stage(self, *, task_id: str, run_id: str, stage: str, attempt: int | None, agent: AgentRuntime, access: str, cwd: Path, inputs: tuple[tuple[str, Path], ...], schema_name: str, output_name: str, failure_code: str='agent_protocol_invalid', notes: tuple[str, ...]=()) -> StoredArtifact:
        stage_attempt = attempt or 1
        stage_db_id = self.tasks.start_stage(run_id, stage, stage_attempt)
        stage_root = self.artifacts.stage_root(task_id, run_id, stage, attempt)
        output_path = stage_root / output_name
        schema_path = self.artifacts.schema_registry.schema_path(schema_name)
        entry_artifact = self.artifacts.write_text(stage_root / 'entry.md', render_stage_entry(StageEntry(task_id=task_id, run_id=run_id, stage=stage, attempt=attempt, inputs=inputs, output_path=output_path, schema_path=schema_path, notes=notes)))
        self._index(run_id, stage, 'entry', entry_artifact, attempt)
        result = agent.run(AgentRequest(stage='repair' if stage == 'repair' else 'discovery', entry_file=entry_artifact.path, cwd=cwd, access='workspace_write' if access == 'workspace_write' else 'read_only', output_schema=schema_path, cancel_check=lambda: self.tasks.is_cancel_requested(run_id)))
        diagnostic = self.artifacts.write_json(
            stage_root / 'agent-runtime.json',
            {
                'schema_version': 1,
                'runtime': str(getattr(agent, 'runtime_name', 'unknown')),
                'status': result.status,
                'exit_code': result.exit_code,
                'session_id': result.session_id,
                'duration_seconds': result.duration_seconds,
                'usage': result.usage,
                'cost_usd': result.cost_usd,
                'command': list(result.command),
                'stderr': result.stderr,
                'events': list(result.events),
            },
        )
        self._index(run_id, stage, 'agent_runtime', diagnostic, attempt)
        if result.status == 'canceled':
            self.tasks.finish_stage(stage_db_id, status='canceled')
            raise PipelineCanceled()
        if result.status == 'timed_out':
            self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': 'agent_timeout'})
            raise PipelineFailure('agent_timeout', stage, f'{stage} Agent timed out')
        if result.status != 'succeeded':
            reason = self._agent_failure_reason(result)
            self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': 'agent_failed', 'summary': reason, 'diagnostic_path': str(diagnostic.path)})
            raise PipelineFailure(failure_code, stage, f'{stage} Agent failed: {reason}')
        if self.tasks.is_cancel_requested(run_id):
            self.tasks.finish_stage(stage_db_id, status='canceled')
            raise PipelineCanceled()
        try:
            if output_path.is_file():
                payload = json.loads(output_path.read_text(encoding='utf-8'))
            elif isinstance(result.structured_output, dict):
                payload = result.structured_output
            else:
                self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': failure_code})
                raise PipelineFailure(failure_code, stage, f'{stage} Agent produced no structured result')
            artifact = self.artifacts.write_json(output_path, payload, schema_name=schema_name, copy_schema=True)
        except (ArtifactProtocolError, json.JSONDecodeError) as exc:
            self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': failure_code, 'summary': str(exc)})
            raise PipelineFailure(failure_code, stage, f'{stage} Agent output is invalid: {exc}') from exc
        self._index(run_id, stage, schema_name, artifact, attempt)
        self.tasks.finish_stage(stage_db_id, status='completed', output_path=str(artifact.path))
        return artifact

    def _run_markdown_agent_stage(self, *, task_id: str, run_id: str, agent: AgentRuntime, cwd: Path, inputs: tuple[tuple[str, Path], ...], notes: tuple[str, ...]) -> StoredArtifact:
        stage = 'discovery'
        stage_db_id = self.tasks.start_stage(run_id, stage, 1)
        stage_root = self.artifacts.stage_root(task_id, run_id, stage)
        output_path = stage_root / 'localization-report.md'
        entry_artifact = self.artifacts.write_text(
            stage_root / 'entry.md',
            render_stage_entry(StageEntry(task_id=task_id, run_id=run_id, stage=stage, attempt=None, inputs=inputs, output_path=output_path, notes=tuple(item for item in notes if item))),
        )
        self._index(run_id, stage, 'entry', entry_artifact)
        result = agent.run(AgentRequest(stage='discovery', entry_file=entry_artifact.path, cwd=cwd, access='read_only', output_schema=None, cancel_check=lambda: self.tasks.is_cancel_requested(run_id)))
        diagnostic = self.artifacts.write_json(stage_root / 'agent-runtime.json', {'schema_version': 1, 'runtime': str(getattr(agent, 'runtime_name', 'unknown')), 'status': result.status, 'exit_code': result.exit_code, 'session_id': result.session_id, 'duration_seconds': result.duration_seconds, 'usage': result.usage, 'cost_usd': result.cost_usd, 'command': list(result.command), 'stderr': result.stderr, 'events': list(result.events)})
        self._index(run_id, stage, 'agent_runtime', diagnostic)
        if result.status == 'canceled':
            self.tasks.finish_stage(stage_db_id, status='canceled')
            raise PipelineCanceled()
        if result.status == 'timed_out':
            summary = 'Localization Agent timed out'
            self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': 'agent_timeout', 'summary': summary})
            raise PipelineFailure('agent_timeout', stage, summary)
        if result.status != 'succeeded':
            reason = self._agent_failure_reason(result)
            self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': 'scope_discovery_failed', 'summary': reason})
            raise PipelineFailure('scope_discovery_failed', stage, f'Localization Agent failed: {reason}')
        report = str(result.final_text or '').strip()
        if not report:
            self.tasks.finish_stage(stage_db_id, status='failed', failure={'code': 'scope_discovery_failed', 'summary': 'Localization Agent returned an empty report'})
            raise PipelineFailure('scope_discovery_failed', stage, 'Localization Agent returned an empty report')
        artifact = self.artifacts.write_text(output_path, report + '\n')
        self._index(run_id, stage, 'localization_report', artifact)
        self.tasks.finish_stage(stage_db_id, status='completed', output_path=str(artifact.path))
        return artifact

    @staticmethod
    def _agent_failure_reason(result: Any) -> str:
        for event in reversed(result.events):
            if str(event.get('type', '')) not in {'error', 'turn.failed'}:
                continue
            error = event.get('error')
            if isinstance(error, dict) and error.get('message'):
                return str(error['message'])[:1200]
            if event.get('message'):
                return str(event['message'])[:1200]
        stderr = result.stderr.strip()
        if stderr:
            return str(stderr.splitlines()[-1])[:1200]
        return f'process exited with code {result.exit_code}'

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
