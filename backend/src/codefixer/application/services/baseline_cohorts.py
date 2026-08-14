from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from codefixer.application.ports.sources import (
    CandidateChange,
    ModificationSourceAdapter,
    SourcePolicy,
    WorkspaceManifest,
)
from codefixer.infrastructure.baseline_cohorts import (
    BaselineCohortMembership,
    BaselineCohortStore,
)
from codefixer.infrastructure.database import connect_database
from codefixer.infrastructure.leases import LeaseBusyError, LeaseStore

DEFAULT_BASELINE_COHORT_WINDOW_MS = 2000


class BaselineCohortCanceled(RuntimeError):
    pass


class BaselineCohortResolutionError(RuntimeError):
    def __init__(self, failure: dict[str, object]):
        self.failure = failure
        super().__init__(str(failure.get("summary", "baseline cohort resolution failed")))


@dataclass(frozen=True)
class BaselineResolution:
    cohort_id: str
    cohort_key: str
    revision: str
    leader_task_run_id: str
    task_run_id: str
    is_leader: bool


def build_baseline_cohort_key(
    *, repository_root: Path, source_type: str, baseline_identity: str
) -> str:
    """Return an opaque key without leaking a local path or repository URL to lease logs."""

    normalized_path = os.path.normcase(str(repository_root.resolve())).replace("\\", "/")
    payload = json.dumps(
        {
            "repository_root": normalized_path,
            "source_type": source_type,
            "baseline_identity": baseline_identity.strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"baseline:{hashlib.sha256(payload.encode('utf-8')).hexdigest()}"


class BaselineCohortCoordinator:
    """Join a short cohort and ensure only its leader resolves the shared baseline."""

    def __init__(
        self,
        db_path: Path,
        *,
        window_ms: int = DEFAULT_BASELINE_COHORT_WINDOW_MS,
        poll_interval_seconds: float = 0.05,
        refresh_lease_ttl_seconds: int = 300,
    ) -> None:
        if window_ms < 0:
            raise ValueError("baseline cohort window cannot be negative")
        if poll_interval_seconds <= 0:
            raise ValueError("baseline cohort poll interval must be positive")
        if refresh_lease_ttl_seconds < 3:
            raise ValueError("baseline refresh lease TTL must be at least 3 seconds")
        self.db_path = db_path
        self.window_ms = window_ms
        self.poll_interval_seconds = poll_interval_seconds
        self.refresh_lease_ttl_seconds = refresh_lease_ttl_seconds

    def resolve(
        self,
        *,
        cohort_key: str,
        source_type: str,
        task_run_id: str,
        resolver: Callable[[], str],
        cancel_check: Callable[[], bool] | None = None,
    ) -> BaselineResolution:
        membership = self._join(
            cohort_key=cohort_key,
            source_type=source_type,
            task_run_id=task_run_id,
        )
        if membership.is_leader and membership.baseline_revision is None:
            self._resolve_as_leader(membership, resolver, cancel_check)
        return self._wait_for_resolution(task_run_id, cancel_check)

    def _join(
        self, *, cohort_key: str, source_type: str, task_run_id: str
    ) -> BaselineCohortMembership:
        with connect_database(self.db_path) as connection:
            return BaselineCohortStore(connection).join_or_create(
                cohort_key=cohort_key,
                source_type=source_type,
                task_run_id=task_run_id,
                window_ms=self.window_ms,
            )

    def _resolve_as_leader(
        self,
        membership: BaselineCohortMembership,
        resolver: Callable[[], str],
        cancel_check: Callable[[], bool] | None,
    ) -> None:
        resource_key = f"baseline-refresh:{membership.cohort_key.removeprefix('baseline:')}"
        owner = f"{membership.cohort_id}:{uuid.uuid4()}"
        while True:
            if cancel_check is not None and bool(cancel_check()):
                failure = {
                    "code": "baseline_leader_canceled",
                    "stage": "prepare",
                    "summary": "Baseline cohort leader was canceled before resolving the source",
                    "retryable": True,
                    "side_effects": [],
                }
                self._fail(membership, failure)
                raise BaselineCohortCanceled(str(failure["summary"]))
            try:
                with connect_database(self.db_path) as connection:
                    LeaseStore(connection).acquire(
                        resource_key, owner, ttl_seconds=self.refresh_lease_ttl_seconds
                    )
                break
            except LeaseBusyError:
                time.sleep(self.poll_interval_seconds)

        heartbeat_stop = threading.Event()
        lease_lost = threading.Event()

        def heartbeat() -> None:
            interval = max(1.0, self.refresh_lease_ttl_seconds / 3)
            while not heartbeat_stop.wait(interval):
                try:
                    with connect_database(self.db_path) as connection:
                        LeaseStore(connection).heartbeat(
                            resource_key,
                            owner,
                            ttl_seconds=self.refresh_lease_ttl_seconds,
                        )
                except LeaseBusyError:
                    lease_lost.set()
                    return

        heartbeat_thread = threading.Thread(
            target=heartbeat,
            name=f"codefixer-baseline-{membership.cohort_id}",
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            latest = self._get(membership.task_run_id)
            if latest.baseline_revision is not None:
                return
            revision = resolver().strip()
            if not revision:
                raise ValueError("source baseline resolver returned an empty revision")
            if lease_lost.is_set():
                raise LeaseBusyError("baseline refresh lease was lost during resolution")
            with connect_database(self.db_path) as connection:
                BaselineCohortStore(connection).resolve(
                    cohort_id=membership.cohort_id,
                    leader_task_run_id=membership.task_run_id,
                    baseline_revision=revision,
                )
        except BaselineCohortCanceled:
            raise
        except Exception as exc:
            failure = {
                "code": "baseline_resolution_failed",
                "stage": "prepare",
                "summary": str(exc),
                "retryable": True,
                "side_effects": [],
            }
            self._fail(membership, failure)
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=2)
            with connect_database(self.db_path) as connection:
                LeaseStore(connection).release(resource_key, owner)

    def _wait_for_resolution(
        self, task_run_id: str, cancel_check: Callable[[], bool] | None
    ) -> BaselineResolution:
        while True:
            if cancel_check is not None and bool(cancel_check()):
                raise BaselineCohortCanceled(
                    "task was canceled while waiting for the shared baseline"
                )
            membership = self._get(task_run_id)
            if membership.failure is not None:
                raise BaselineCohortResolutionError(membership.failure)
            if membership.baseline_revision is not None:
                return BaselineResolution(
                    cohort_id=membership.cohort_id,
                    cohort_key=membership.cohort_key,
                    revision=membership.baseline_revision,
                    leader_task_run_id=membership.leader_task_run_id,
                    task_run_id=membership.task_run_id,
                    is_leader=membership.is_leader,
                )
            time.sleep(self.poll_interval_seconds)

    def _get(self, task_run_id: str) -> BaselineCohortMembership:
        with connect_database(self.db_path) as connection:
            return BaselineCohortStore(connection).get_for_task(task_run_id)

    def _fail(
        self, membership: BaselineCohortMembership, failure: dict[str, object]
    ) -> None:
        with connect_database(self.db_path) as connection:
            BaselineCohortStore(connection).fail(
                cohort_id=membership.cohort_id,
                leader_task_run_id=membership.task_run_id,
                failure=failure,
            )


class CohortSourceAdapter:
    """ModificationSourceAdapter decorator for the one-line pipeline integration point.

    Only the first ``prepare`` call for a TaskRun resolves a source baseline. Later
    workspaces pass the already-frozen revision through unchanged.
    """

    def __init__(
        self,
        source: ModificationSourceAdapter,
        coordinator: BaselineCohortCoordinator,
        *,
        repository_root: Path,
        baseline_identity: str,
        baseline_resolver: Callable[[], str] | None = None,
        cancel_check: Callable[[str], bool] | None = None,
    ) -> None:
        self.source = source
        self.coordinator = coordinator
        self.source_type = source.source_type
        self.cancel_check = cancel_check
        self.baseline_resolver = baseline_resolver or source.current_revision
        self.cohort_key = build_baseline_cohort_key(
            repository_root=repository_root,
            source_type=source.source_type,
            baseline_identity=baseline_identity,
        )

    def current_revision(self) -> str:
        # 修改源的稳定性以权威远端为准；本地缓存的 HEAD 可能故意保持不动。
        return str(self.baseline_resolver())

    def prepare(
        self,
        *,
        source_id: str,
        run_id: str,
        workspace_path: Path,
        base_revision: str | None = None,
    ) -> WorkspaceManifest:
        if base_revision is not None:
            return self.source.prepare(
                source_id=source_id,
                run_id=run_id,
                workspace_path=workspace_path,
                base_revision=base_revision,
            )
        task_run_id = run_id.split(":", 1)[0]
        resolution = self.coordinator.resolve(
            cohort_key=self.cohort_key,
            source_type=self.source_type,
            task_run_id=task_run_id,
            resolver=self.baseline_resolver,
            cancel_check=(
                (lambda: bool(self.cancel_check and self.cancel_check(task_run_id)))
                if self.cancel_check is not None
                else None
            ),
        )
        manifest = self.source.prepare(
            source_id=source_id,
            run_id=run_id,
            workspace_path=workspace_path,
            base_revision=resolution.revision,
        )
        return replace(manifest, baseline_cohort_id=resolution.cohort_id)

    def collect_change(
        self, manifest: WorkspaceManifest, policy: SourcePolicy
    ) -> CandidateChange:
        return self.source.collect_change(manifest, policy)

    def restore_candidate(
        self, manifest: WorkspaceManifest, candidate: CandidateChange
    ) -> None:
        self.source.restore_candidate(manifest, candidate)

    def cleanup(self, manifest: WorkspaceManifest) -> None:
        self.source.cleanup(manifest)
