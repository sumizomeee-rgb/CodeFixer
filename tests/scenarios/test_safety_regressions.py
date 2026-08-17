from __future__ import annotations

import subprocess
from pathlib import Path

from codefixer.adapters.delivery_patch import PatchFinalAction
from codefixer.adapters.sources.directory import DirectReadOnlySourceAdapter
from codefixer.adapters.sources.git import GitSourceAdapter
from codefixer.application.ports.agents import AgentRunResult
from codefixer.application.ports.sources import SourcePolicy
from codefixer.application.services.delivery import DeliveryCoordinator
from codefixer.application.services.stability import PreDeliveryStabilityGuard
from codefixer.application.services.verification import (
    VerificationRunner,
    VerificationStep,
)
from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.artifact_index import ArtifactIndex
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.delivery_store import DeliveryStore
from codefixer.infrastructure.task_store import TaskStore
from codefixer.orchestration import ChangedPipeline
from codefixer.protocols import ArtifactStore, SchemaRegistry

ROOT = Path(__file__).resolve().parents[2]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True, capture_output=True
    ).stdout.strip()


def create_repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    (root / "src").mkdir()
    (root / "src/app.py").write_text("def get_value():\n    return 1\n", encoding="utf-8")
    (root / "README.md").write_text("safe\n", encoding="utf-8")
    git(root, "init")
    git(root, "config", "user.email", "test@codefixer.local")
    git(root, "config", "user.name", "Test")
    git(root, "add", ".")
    git(root, "commit", "-m", "base")
    return root, git(root, "rev-parse", "HEAD")


class Discovery:
    runtime_name = "fake"

    def __init__(self, report: str = "# 定位报告\n\n目标位于 `src/app.py`。") -> None:
        self.report = report
        self.calls = 0

    def run(self, request):
        self.calls += 1
        return AgentRunResult(
            status="succeeded",
            exit_code=0,
            session_id="discovery",
            structured_output=None,
            final_text=self.report,
        )


class Coding:
    runtime_name = "fake"

    def __init__(self, *, unauthorized: bool = False) -> None:
        self.calls = 0
        self.unauthorized = unauthorized

    def run(self, request):
        self.calls += 1
        (request.cwd / "src/app.py").write_text(
            "def get_value():\n    return 2\n", encoding="utf-8"
        )
        changed = ["src/app.py"]
        if self.unauthorized:
            (request.cwd / "README.md").write_text("mutated\n", encoding="utf-8")
            changed.append("README.md")
        return AgentRunResult(
            status="succeeded",
            exit_code=0,
            session_id="coding",
            structured_output={
                "schema_version": 1,
                "outcome": "changed",
                "summary": "Update the stale value.",
                "module_name": "app",
                "change_summary": "修正返回值",
                "changed_paths_claimed": changed,
                "checks_requested": [],
                "limitations": [],
                "blocking_code": None,
                "blocking_evidence_ids": [],
            },
        )


class NeverCoding:
    runtime_name = "fake"

    def run(self, request):
        raise AssertionError("Coding Agent must not run")


class LatestTicketProvider:
    def __init__(self, latest: IngestedTicket) -> None:
        self.latest = latest

    def fetch(self, external_ticket_id: str) -> IngestedTicket:
        assert external_ticket_id == self.latest.external_ticket_id
        return self.latest


class StableSourceView:
    def __init__(self, source: GitSourceAdapter) -> None:
        self.source = source

    def current_revision(self) -> str:
        return self.source.current_revision()


def build_pipeline(
    *,
    tmp_path: Path,
    tasks: TaskStore,
    connection,
    source: GitSourceAdapter,
    discovery,
    coding,
    stability_guard=None,
    verification_steps: tuple[VerificationStep, ...] = (),
) -> ChangedPipeline:
    data = tmp_path / "data"
    repository = source.repository_path
    return ChangedPipeline(
        tasks=tasks,
        artifacts=ArtifactStore(data, SchemaRegistry(ROOT / "contracts")),
        artifact_index=ArtifactIndex(connection, data),
        source=source,
        localization_source=DirectReadOnlySourceAdapter(
            repository, source.current_revision, source_type="git"
        ),
        discovery_agent=discovery,
        repair_agent=coding,
        verification_runner=VerificationRunner(),
        verification_steps=verification_steps,
        project={
            "id": "project-a",
            "localizationSource": {
                "id": "project-source",
                "type": "git",
                "path": str(repository),
            },
            "modificationWorkspace": {
                "id": "project-source",
                "path": str(repository),
                "vcsKind": "git",
                "allowedRoots": ["src"],
                "allowedExtensions": [".py"],
            },
        },
        source_policy=SourcePolicy(allowed_roots=("src",), allowed_extensions=(".py",)),
        delivery=DeliveryCoordinator(
            (
                PatchFinalAction(
                    action_id="primary-patch",
                    action_version=1,
                    store=DeliveryStore(connection),
                    output_directory=data / "patches",
                ),
            )
        ),
        stability_guard=stability_guard,
    )


def ingest(tasks: TaskStore, ticket: IngestedTicket) -> tuple[dict, str]:
    task = tasks.ingest(ticket, "project-a", "automatic")
    return task, task["runs"][0]["id"]


def test_pipeline_invokes_each_agent_once(tmp_path: Path):
    repository, _ = create_repo(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    with connect_database(data / "codefixer.db") as connection:
        apply_migrations(connection)
        tasks = TaskStore(connection)
        task, run_id = ingest(
            tasks, IngestedTicket("fake", "BUG-ONCE", "Once", {"description": "wrong"})
        )
        discovery = Discovery()
        coding = Coding()
        result = build_pipeline(
            tmp_path=tmp_path,
            tasks=tasks,
            connection=connection,
            source=GitSourceAdapter(repository, ["git"]),
            discovery=discovery,
            coding=coding,
        ).run(run_id)
        assert result.status == "completed" and result.result == "changed"
        assert discovery.calls == 1 and coding.calls == 1
        frozen = data / "tasks" / task["id"] / "runs" / run_id / "freeze-change/files/src/app.py"
        assert "return 2" in frozen.read_text(encoding="utf-8")
        assert git(repository, "status", "--porcelain") == ""


def test_unauthorized_path_fails_before_verification_or_delivery(tmp_path: Path):
    repository, _ = create_repo(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    with connect_database(data / "codefixer.db") as connection:
        apply_migrations(connection)
        tasks = TaskStore(connection)
        task, run_id = ingest(
            tasks, IngestedTicket("fake", "BUG-SCOPE", "Scope", {"description": "wrong"})
        )
        result = build_pipeline(
            tmp_path=tmp_path,
            tasks=tasks,
            connection=connection,
            source=GitSourceAdapter(repository, ["git"]),
            discovery=Discovery(),
            coding=Coding(unauthorized=True),
        ).run(run_id)
        assert result.status == "failed"
        assert tasks.get_task(task["id"])["failure"]["code"] == "unauthorized_change"
        assert not (data / "patches").exists()
        assert not (data / "tasks" / task["id"] / "runs" / run_id / "freeze-change").exists()
        assert git(repository, "status", "--porcelain") == ""


def test_ticket_change_after_coding_blocks_freeze_and_delivery(tmp_path: Path):
    repository, _ = create_repo(tmp_path)
    source = GitSourceAdapter(repository, ["git"])
    data = tmp_path / "data"
    data.mkdir()
    frozen = IngestedTicket(
        "fake", "BUG-STALE", "Stale", {"description": "original"}, "v1", True
    )
    latest = IngestedTicket(
        "fake", "BUG-STALE", "Stale", {"description": "changed"}, "v2", True
    )
    guard = PreDeliveryStabilityGuard(LatestTicketProvider(latest), StableSourceView(source))
    with connect_database(data / "codefixer.db") as connection:
        apply_migrations(connection)
        tasks = TaskStore(connection)
        task, run_id = ingest(tasks, frozen)
        result = build_pipeline(
            tmp_path=tmp_path,
            tasks=tasks,
            connection=connection,
            source=source,
            discovery=Discovery(),
            coding=Coding(),
            stability_guard=guard,
        ).run(run_id)
        assert result.status == "failed"
        assert tasks.get_task(task["id"])["failure"]["code"] == "ticket_changed_during_run"
        assert not (data / "patches").exists()
        assert not (data / "tasks" / task["id"] / "runs" / run_id / "freeze-change").exists()
        assert git(repository, "status", "--porcelain") == ""


def test_empty_localization_report_stops_before_coding(tmp_path: Path):
    repository, _ = create_repo(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    with connect_database(data / "codefixer.db") as connection:
        apply_migrations(connection)
        tasks = TaskStore(connection)
        task, run_id = ingest(
            tasks, IngestedTicket("fake", "BUG-NO-SCOPE", "Unknown", {"description": "none"})
        )
        result = build_pipeline(
            tmp_path=tmp_path,
            tasks=tasks,
            connection=connection,
            source=GitSourceAdapter(repository, ["git"]),
            discovery=Discovery("  "),
            coding=NeverCoding(),
        ).run(run_id)
        assert result.status == "failed"
        detail = tasks.get_task(task["id"])
        assert detail["failure"]["code"] == "scope_discovery_failed"
        stage = next(item for item in detail["runs"][0]["stages"] if item["stage_id"] == "discovery")
        assert stage["status"] == "failed"


def test_verification_side_effect_is_removed_before_freeze(tmp_path: Path):
    repository, _ = create_repo(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    mutation = VerificationStep(
        "mutating-check",
        (
            "python",
            "-c",
            "from pathlib import Path; Path('src/app.py').write_text('def get_value():\\n    return 99\\n')",
        ),
    )
    with connect_database(data / "codefixer.db") as connection:
        apply_migrations(connection)
        tasks = TaskStore(connection)
        task, run_id = ingest(
            tasks, IngestedTicket("fake", "BUG-VERIFY", "Verify", {"description": "wrong"})
        )
        coding = Coding()
        result = build_pipeline(
            tmp_path=tmp_path,
            tasks=tasks,
            connection=connection,
            source=GitSourceAdapter(repository, ["git"]),
            discovery=Discovery(),
            coding=coding,
            verification_steps=(mutation,),
        ).run(run_id)
        assert result.status == "completed" and coding.calls == 1
        frozen = data / "tasks" / task["id"] / "runs" / run_id / "freeze-change/files/src/app.py"
        assert "return 2" in frozen.read_text(encoding="utf-8")
        assert "return 99" not in frozen.read_text(encoding="utf-8")
        assert git(repository, "status", "--porcelain") == ""
