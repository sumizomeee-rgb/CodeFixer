from __future__ import annotations

import threading
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from codefixer.application.ports.agents import AgentRequest, AgentRunResult
from codefixer.application.services.baseline_cohorts import (
    BaselineCohortCoordinator,
    BaselineCohortResolutionError,
)
from codefixer.application.services.llm_slots import LeasedAgentRuntime, LlmSlotPool
from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.baseline_cohorts import BaselineCohortStore
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.llm_slots import LlmSlotLeaseLostError, LlmSlotStore
from codefixer.infrastructure.task_store import TaskStore


def _database(tmp_path: Path) -> Path:
    db_path = tmp_path / "data" / "codefixer.db"
    with connect_database(db_path) as connection:
        apply_migrations(connection)
    return db_path


def _create_runs(db_path: Path, count: int) -> list[str]:
    run_ids: list[str] = []
    with connect_database(db_path) as connection:
        tasks = TaskStore(connection)
        for index in range(count):
            result = tasks.ingest(
                IngestedTicket("provider", str(index), f"ticket {index}", {}),
                "project",
                "automatic",
            )
            run_ids.append(str(result["runs"][0]["id"]))
    return run_ids


def test_llm_slots_are_fifo_persistent_and_reclaim_expired_lease(tmp_path: Path) -> None:
    db_path = _database(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with connect_database(db_path) as connection:
        slots = LlmSlotStore(connection)
        first_position = slots.enqueue(
            request_id="first", owner="worker:first", stage_id="discovery", now=start
        )
        second_position = slots.enqueue(
            request_id="second", owner="worker:second", stage_id="repair", now=start
        )
        assert first_position < second_position
        first = slots.try_acquire(
            request_id="first",
            owner="worker:first",
            capacity=1,
            ttl_seconds=5,
            now=start,
        )
        assert first is not None
        assert (
            slots.try_acquire(
                request_id="second",
                owner="worker:second",
                capacity=1,
                ttl_seconds=5,
                now=start,
            )
            is None
        )
        assert (
            slots.try_acquire(
                request_id="second",
                owner="worker:second",
                capacity=1,
                ttl_seconds=5,
                now=start + timedelta(seconds=4),
            )
            is None
        )

    with connect_database(db_path) as connection:
        slots = LlmSlotStore(connection)
        second = slots.try_acquire(
            request_id="second",
            owner="worker:second",
            capacity=1,
            ttl_seconds=5,
            now=start + timedelta(seconds=6),
        )
        assert second is not None
        assert second.slot_number == 0
        with pytest.raises(LlmSlotLeaseLostError):
            slots.try_acquire(
                request_id="first",
                owner="worker:first",
                capacity=1,
                ttl_seconds=5,
                now=start + timedelta(seconds=6),
            )
        snapshot = slots.snapshot(capacity=1, now=start + timedelta(seconds=6))
        assert (snapshot.active, snapshot.waiting) == (1, 0)


def test_leased_agent_runtime_holds_global_slot_only_while_running(tmp_path: Path) -> None:
    db_path = _database(tmp_path)
    entry = tmp_path / "entry.md"
    entry.write_text("entry", encoding="utf-8")
    active = 0
    maximum_active = 0
    state_lock = threading.Lock()

    class Runtime:
        runtime_name = "fake"

        def run(self, request: AgentRequest) -> AgentRunResult:
            nonlocal active, maximum_active
            with state_lock:
                active += 1
                maximum_active = max(maximum_active, active)
            try:
                time.sleep(0.08)
                return AgentRunResult("succeeded", 0, None, {"ok": True})
            finally:
                with state_lock:
                    active -= 1

    pool = LlmSlotPool(
        db_path,
        capacity=1,
        lease_ttl_seconds=6,
        poll_interval_seconds=0.005,
        owner_prefix="test-worker",
    )
    runtimes = [LeasedAgentRuntime(Runtime(), pool, task_run_id=f"run-{i}") for i in range(2)]
    results: list[AgentRunResult] = []

    def invoke(runtime: LeasedAgentRuntime) -> None:
        results.append(
            runtime.run(
                AgentRequest(
                    stage="discovery",
                    entry_file=entry,
                    cwd=tmp_path,
                    access="read_only",
                )
            )
        )

    threads = [threading.Thread(target=invoke, args=(runtime,)) for runtime in runtimes]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert len(results) == 2
    assert all(result.status == "succeeded" for result in results)
    assert maximum_active == 1
    assert pool.snapshot().active == 0


def test_baseline_cohort_store_shares_revision_then_rolls_window(tmp_path: Path) -> None:
    db_path = _database(tmp_path)
    first_run, second_run, later_run = _create_runs(db_path, 3)
    start = datetime(2026, 1, 1, tzinfo=UTC)
    with connect_database(db_path) as connection:
        cohorts = BaselineCohortStore(connection)
        leader = cohorts.join_or_create(
            cohort_key="source-key",
            source_type="git",
            task_run_id=first_run,
            window_ms=2000,
            now=start,
        )
        follower = cohorts.join_or_create(
            cohort_key="source-key",
            source_type="git",
            task_run_id=second_run,
            window_ms=2000,
            now=start + timedelta(seconds=1),
        )
        assert leader.is_leader
        assert not follower.is_leader
        assert leader.cohort_id == follower.cohort_id
        cohorts.resolve(
            cohort_id=leader.cohort_id,
            leader_task_run_id=first_run,
            baseline_revision="abc123",
            now=start + timedelta(seconds=1),
        )
        shared = cohorts.get_for_task(second_run, now=start + timedelta(seconds=1))
        assert shared.baseline_revision == "abc123"
        assert cohorts.member_count(leader.cohort_id) == 2

        later = cohorts.join_or_create(
            cohort_key="source-key",
            source_type="git",
            task_run_id=later_run,
            window_ms=2000,
            now=start + timedelta(seconds=3),
        )
        assert later.is_leader
        assert later.cohort_id != leader.cohort_id
        assert cohorts.get_for_task(first_run, now=start + timedelta(seconds=3)).state == "sealed"


def test_baseline_coordinator_calls_only_the_leader_resolver(tmp_path: Path) -> None:
    db_path = _database(tmp_path)
    run_ids = _create_runs(db_path, 2)
    coordinator = BaselineCohortCoordinator(
        db_path,
        window_ms=500,
        poll_interval_seconds=0.005,
        refresh_lease_ttl_seconds=6,
    )
    start = threading.Barrier(2)
    resolver_calls = 0
    resolver_lock = threading.Lock()
    results = []

    def worker(run_id: str) -> None:
        nonlocal resolver_calls
        start.wait(timeout=2)

        def resolver() -> str:
            nonlocal resolver_calls
            with resolver_lock:
                resolver_calls += 1
            time.sleep(0.08)
            return "shared-sha"

        results.append(
            coordinator.resolve(
                cohort_key="same-source",
                source_type="git",
                task_run_id=run_id,
                resolver=resolver,
            )
        )

    threads = [threading.Thread(target=worker, args=(run_id,)) for run_id in run_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert resolver_calls == 1
    assert {result.revision for result in results} == {"shared-sha"}
    assert len({result.cohort_id for result in results}) == 1
    assert {result.is_leader for result in results} == {True, False}


def test_baseline_coordinator_shares_leader_failure_with_followers(tmp_path: Path) -> None:
    db_path = _database(tmp_path)
    run_ids = _create_runs(db_path, 2)
    coordinator = BaselineCohortCoordinator(
        db_path,
        window_ms=500,
        poll_interval_seconds=0.005,
        refresh_lease_ttl_seconds=6,
    )
    start = threading.Barrier(2)
    failures: list[dict[str, object]] = []

    def fail_resolution() -> str:
        raise RuntimeError("remote unavailable")

    def worker(run_id: str) -> None:
        start.wait(timeout=2)
        try:
            coordinator.resolve(
                cohort_key="broken-source",
                source_type="svn",
                task_run_id=run_id,
                resolver=fail_resolution,
            )
        except BaselineCohortResolutionError as exc:
            failures.append(exc.failure)

    threads = [threading.Thread(target=worker, args=(run_id,)) for run_id in run_ids]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert all(not thread.is_alive() for thread in threads)
    assert len(failures) == 2
    assert {failure["code"] for failure in failures} == {"baseline_resolution_failed"}
    assert {failure["summary"] for failure in failures} == {"remote unavailable"}
