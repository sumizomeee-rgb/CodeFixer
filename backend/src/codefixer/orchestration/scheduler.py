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
        for provider in loaded.config.ticketProviders:
            provider_id = str(provider.get("id", ""))
            if not provider_id or provider.get("enabled", True) is False:
                continue
            interval = max(5, int(provider.get("pollIntervalSeconds", 60)))
            previous = self._provider_last_poll.get(provider_id, float("-inf"))
            if now - previous < interval:
                continue
            self._provider_last_poll[provider_id] = now
            await asyncio.to_thread(self._poll_provider, dict(provider))

        capacity = loaded.config.execution.maxConcurrentTasks - len(self._active)
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
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.sleep_seconds)
            except TimeoutError:
                continue

    def _execute(self, run_id: str) -> object:
        if self._execute_override is not None:
            return self._execute_override(run_id)
        with connect_database(self.db_path) as connection:
            executor = RunExecutor(
                connection=connection,
                config_store=self.config_store,
                contracts_root=self.contracts_root,
            )
            return executor.execute(run_id)

    def _poll_provider(self, provider: dict[str, object]) -> None:
        loaded = self.config_store.reload()
        with connect_database(self.db_path) as connection:
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
