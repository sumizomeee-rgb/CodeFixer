from __future__ import annotations

import os
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from codefixer.application.ports.agents import AgentRequest, AgentRunResult, AgentRuntime
from codefixer.infrastructure.database import connect_database
from codefixer.infrastructure.llm_slots import (
    LlmSlotLease,
    LlmSlotLeaseLostError,
    LlmSlotSnapshot,
    LlmSlotStore,
)

DEFAULT_MAX_CONCURRENT_LLM_CALLS = 4


class LlmSlotPool:
    """Blocking facade over the durable FIFO slot store.

    Database connections are deliberately short-lived. The process never keeps a
    SQLite write transaction open while waiting for a slot or running an Agent.
    """

    def __init__(
        self,
        db_path: Path,
        *,
        capacity: int = DEFAULT_MAX_CONCURRENT_LLM_CALLS,
        lease_ttl_seconds: int = 60,
        poll_interval_seconds: float = 0.05,
        owner_prefix: str | None = None,
    ) -> None:
        if capacity < 1:
            raise ValueError("LLM slot capacity must be positive")
        if lease_ttl_seconds < 3:
            raise ValueError("LLM slot lease TTL must be at least 3 seconds")
        if poll_interval_seconds <= 0:
            raise ValueError("LLM slot poll interval must be positive")
        self.db_path = db_path
        self.capacity = capacity
        self.lease_ttl_seconds = lease_ttl_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.owner_prefix = owner_prefix or f"worker-{os.getpid()}"

    def acquire(
        self,
        *,
        stage_id: str,
        task_run_id: str | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> LlmSlotLease | None:
        request_id = str(uuid.uuid4())
        owner = f"{self.owner_prefix}:{request_id}"
        with connect_database(self.db_path) as connection:
            LlmSlotStore(connection).enqueue(
                request_id=request_id,
                owner=owner,
                task_run_id=task_run_id,
                stage_id=stage_id,
                ttl_seconds=self.lease_ttl_seconds,
            )
        while True:
            if cancel_check is not None and bool(cancel_check()):
                with connect_database(self.db_path) as connection:
                    LlmSlotStore(connection).cancel_waiter(
                        request_id=request_id, owner=owner
                    )
                return None
            with connect_database(self.db_path) as connection:
                lease = LlmSlotStore(connection).try_acquire(
                    request_id=request_id,
                    owner=owner,
                    capacity=self.capacity,
                    ttl_seconds=self.lease_ttl_seconds,
                )
            if lease is not None:
                return lease
            time.sleep(self.poll_interval_seconds)

    def heartbeat(self, lease: LlmSlotLease) -> LlmSlotLease:
        with connect_database(self.db_path) as connection:
            return LlmSlotStore(connection).heartbeat(
                lease, ttl_seconds=self.lease_ttl_seconds
            )

    def release(self, lease: LlmSlotLease) -> bool:
        with connect_database(self.db_path) as connection:
            return LlmSlotStore(connection).release(lease)

    def snapshot(self) -> LlmSlotSnapshot:
        with connect_database(self.db_path) as connection:
            return LlmSlotStore(connection).snapshot(capacity=self.capacity)


class LeasedAgentRuntime:
    """AgentRuntime decorator that leases one global LLM slot per subprocess run."""

    def __init__(
        self,
        runtime: AgentRuntime,
        pool: LlmSlotPool,
        *,
        task_run_id: str | None = None,
    ) -> None:
        self.runtime = runtime
        self.pool = pool
        self.task_run_id = task_run_id
        self.runtime_name = runtime.runtime_name

    def run(self, request: AgentRequest) -> AgentRunResult:
        wait_started = time.monotonic()
        lease = self.pool.acquire(
            stage_id=request.stage,
            task_run_id=self.task_run_id,
            cancel_check=request.cancel_check,
        )
        if lease is None:
            return AgentRunResult(
                status="canceled",
                exit_code=None,
                session_id=None,
                structured_output=None,
                events=({"type": "llm_slot_wait_canceled"},),
            )

        wait_seconds = time.monotonic() - wait_started
        heartbeat_stop = threading.Event()
        lease_lost = threading.Event()

        def heartbeat() -> None:
            current = lease
            interval = max(1.0, self.pool.lease_ttl_seconds / 3)
            while not heartbeat_stop.wait(interval):
                try:
                    current = self.pool.heartbeat(current)
                except LlmSlotLeaseLostError:
                    lease_lost.set()
                    return

        heartbeat_thread = threading.Thread(
            target=heartbeat,
            name=f"codefixer-llm-slot-{lease.slot_number}",
            daemon=True,
        )
        heartbeat_thread.start()

        original_cancel = request.cancel_check

        def combined_cancel() -> bool:
            return lease_lost.is_set() or (
                original_cancel is not None and bool(original_cancel())
            )

        try:
            result = self.runtime.run(replace(request, cancel_check=combined_cancel))
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=2)
            self.pool.release(lease)

        slot_event: dict[str, object] = {
            "type": "llm_slot",
            "slot_number": lease.slot_number,
            "queue_position": lease.queue_position,
            "wait_seconds": wait_seconds,
        }
        if lease_lost.is_set():
            message = "global LLM slot lease was lost while the Agent was running"
            return replace(
                result,
                status="failed",
                stderr=f"{result.stderr.rstrip()}\n{message}".lstrip(),
                events=(*result.events, slot_event, {"type": "llm_slot_lease_lost"}),
            )
        return replace(result, events=(*result.events, slot_event))
