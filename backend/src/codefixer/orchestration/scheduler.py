from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from pathlib import Path

from codefixer.application.services.ingestion import poll_configured_provider
from codefixer.infrastructure.config_store import ConfigStore
from codefixer.infrastructure.database import connect_database
from codefixer.infrastructure.task_store import TaskStore
from codefixer.orchestration.factory import RunExecutor
from codefixer.orchestration.recovery import RecoveryService

DEFAULT_MAX_CONCURRENT_TASKS = 8
PROVIDER_FAILURE_BACKOFF_SECONDS = 15 * 60


def _active_provider_ids(projects: list[dict[str, object]]) -> set[str]:
    provider_ids: set[str] = set()
    for project in projects:
        if project.get("enabled", True) is False:
            continue
        for rule in project.get("routingRules") or []:
            if not isinstance(rule, dict):
                continue
            provider_id = str(rule.get("providerRef") or "").strip()
            if provider_id:
                provider_ids.add(provider_id)
    return provider_ids


class Scheduler:
    def __init__(
        self,
        *,
        db_path: Path,
        config_store: ConfigStore,
        contracts_root: Path,
        sleep_seconds: float = 1.0,
        execute_run: Callable[[str], object] | None = None,
    ) -> None:
        self.db_path = db_path
        self.config_store = config_store
        self.contracts_root = contracts_root
        self.sleep_seconds = sleep_seconds
        self._execute_override = execute_run
        self._stop = asyncio.Event()
        self._loop_task: asyncio.Task[None] | None = None
        self._active: dict[str, asyncio.Task[object]] = {}
        self._provider_last_poll: dict[str, float] = {}
        self._provider_retry_after: dict[str, float] = {}

    def start(self) -> None:
        if self._loop_task is None:
            with connect_database(self.db_path) as connection:
                RecoveryService(connection, self.config_store.loaded.data_root).recover_interrupted_runs()
            self._loop_task = asyncio.create_task(self._run_loop(), name="codefixer-scheduler")

    async def stop(self) -> None:
        self._stop.set()
        if self._loop_task is not None:
            await self._loop_task
        if self._active:
            await asyncio.gather(*self._active.values(), return_exceptions=True)

    async def tick(self) -> None:
        self._reap()
        loaded = self.config_store.reload()
        now = time.monotonic()
        active_provider_ids = _active_provider_ids(loaded.config.projects)
        for provider in loaded.config.ticketProviders:
            provider_id = str(provider.get("id", ""))
            if (
                not provider_id
                or provider.get("enabled", True) is False
                or provider_id not in active_provider_ids
                or now < self._provider_retry_after.get(provider_id, 0)
            ):
                continue
            interval = max(5, int(provider.get("pollIntervalSeconds", 60)))
            previous = self._provider_last_poll.get(provider_id, float("-inf"))
            if now - previous < interval:
                continue
            self._provider_last_poll[provider_id] = now
            try:
                await asyncio.to_thread(self._poll_provider, dict(provider))
            except Exception:
                # A broken ticket source must not starve other providers or already-queued repairs.
                # 管理员仍可通过“测试连接”看到反馈源的具体连接错误。
                self._provider_retry_after[provider_id] = (
                    time.monotonic() + PROVIDER_FAILURE_BACKOFF_SECONDS
                )
                continue
            self._provider_retry_after.pop(provider_id, None)

        configured_limit = getattr(
            loaded.config.execution, "maxConcurrentTasks", DEFAULT_MAX_CONCURRENT_TASKS
        )
        max_concurrent_tasks = max(1, int(configured_limit))
        capacity = max_concurrent_tasks - len(self._active)
        if capacity <= 0:
            return
        with connect_database(self.db_path) as connection:
            queued = TaskStore(connection).list_queued_run_ids(capacity)
        for run_id in queued:
            if run_id in self._active:
                continue
            task = asyncio.create_task(
                asyncio.to_thread(self._execute, run_id), name=f"codefixer-run-{run_id}"
            )
            self._active[run_id] = task

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            try:
                await self.tick()
            except Exception:
                # The next tick is still allowed to make progress; persistent task truth is in SQLite.
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.sleep_seconds)
            except TimeoutError:
                continue

    def _execute(self, run_id: str) -> object:
        if self._execute_override is not None:
            return self._execute_override(run_id)
        try:
            with connect_database(self.db_path) as connection:
                executor = RunExecutor(
                    connection=connection,
                    config_store=self.config_store,
                    contracts_root=self.contracts_root,
                )
                return executor.execute(run_id)
        except Exception as exc:
            # No unexpected Python exception is allowed to leave a durable run stuck in "running".
            with connect_database(self.db_path) as connection:
                tasks = TaskStore(connection)
                try:
                    tasks.fail_run(
                        run_id,
                        {
                            "code": "unexpected_executor_error",
                            "stage": "scheduler",
                            "summary": str(exc),
                            "retryable": True,
                            "side_effects": [],
                        },
                    )
                except KeyError:
                    pass
            raise

    def _poll_provider(self, provider: dict[str, object]) -> None:
        loaded = self.config_store.reload()
        provider_id = str(provider.get("id") or "")
        intake_times = [
            str(project.get("intakeStartedAt") or "").strip()
            for project in loaded.config.projects
            if project.get("enabled", True) is not False
            and any(
                isinstance(rule, dict) and str(rule.get("providerRef") or "") == provider_id
                for rule in project.get("routingRules") or []
            )
            and str(project.get("intakeStartedAt") or "").strip()
        ]
        with connect_database(self.db_path) as connection:
            store = TaskStore(connection)
            if store.get_cursor(provider_id) is None and intake_times:
                store.set_cursor(provider_id, min(intake_times))
            poll_configured_provider(
                connection,
                dict(provider),
                loaded.config.projects,
                loaded.config.execution.mode,
                self.config_store.get_secret,
            )

    def _reap(self) -> None:
        finished = [run_id for run_id, task in self._active.items() if task.done()]
        for run_id in finished:
            self._active.pop(run_id, None)
