from __future__ import annotations

import subprocess
from pathlib import Path

from codefixer.adapters.delivery_patch import PatchFinalAction
from codefixer.adapters.sources.directory import DirectReadOnlySourceAdapter
from codefixer.adapters.sources.git import GitSourceAdapter
from codefixer.application.ports.agents import AgentRunResult
from codefixer.application.ports.sources import SourcePolicy
from codefixer.application.services.delivery import DeliveryCoordinator
from codefixer.application.services.verification import VerificationRunner
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


class Discovery:
    runtime_name = "fake"

    def __init__(self, report: str) -> None:
        self.report = report
        self.entry = ""

    def run(self, request):
        self.entry = request.entry_file.read_text(encoding="utf-8")
        return AgentRunResult(
            status="succeeded",
            exit_code=0,
            session_id="discovery",
            structured_output=None,
            final_text=self.report,
        )


class NoChangeCoding:
    runtime_name = "fake"

    def run(self, request):
        return AgentRunResult(
            status="succeeded",
            exit_code=0,
            session_id="coding",
            structured_output={
                "schema_version": 1,
                "outcome": "no_valid_diff",
                "summary": "当前代码无需修改。",
                "module_name": None,
                "change_summary": None,
                "changed_paths_claimed": [],
                "checks_requested": [],
                "limitations": [],
                "blocking_code": None,
                "blocking_evidence_ids": [],
            },
        )


def pipeline(data: Path, connection, tasks: TaskStore, repository: Path, discovery) -> ChangedPipeline:
    source = GitSourceAdapter(repository, ["git"])
    return ChangedPipeline(
        tasks=tasks,
        artifacts=ArtifactStore(data, SchemaRegistry(ROOT / "contracts")),
        artifact_index=ArtifactIndex(connection, data),
        source=source,
        localization_source=DirectReadOnlySourceAdapter(
            repository, source.current_revision, source_type="git"
        ),
        discovery_agent=discovery,
        repair_agent=NoChangeCoding(),
        verification_runner=VerificationRunner(),
        verification_steps=(),
        project={
            "id": "lua",
            "localizationSource": {
                "id": "lua-localization",
                "type": "git",
                "path": str(repository),
            },
            "modificationWorkspace": {
                "id": "lua-code",
                "vcsKind": "git",
                "path": str(repository),
                "allowedRoots": ["src"],
            },
        },
        source_policy=SourcePolicy(allowed_roots=("src",)),
        delivery=DeliveryCoordinator(
            (
                PatchFinalAction(
                    action_id="patch",
                    action_version=1,
                    store=DeliveryStore(connection),
                    output_directory=data / "patches",
                ),
            )
        ),
    )


def test_next_similar_ticket_receives_previous_localization_report(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    (repository / "src").mkdir()
    (repository / "src/app.py").write_text("value = 1\n", encoding="utf-8")
    git(repository, "init")
    git(repository, "config", "user.email", "test@codefixer.local")
    git(repository, "config", "user.name", "Test")
    git(repository, "add", ".")
    git(repository, "commit", "-m", "base")
    data = tmp_path / "data"
    data.mkdir()
    with connect_database(data / "codefixer.db") as connection:
        apply_migrations(connection)
        tasks = TaskStore(connection)
        first = tasks.ingest(
            IngestedTicket(
                "tapd",
                "1253280",
                "【v4.8、trunk】【一键养成-武器养成】武器谐振后品质底未变化",
                {"description": "品质底显示错误"},
            ),
            "lua",
            "automatic",
        )
        first_discovery = Discovery("# 历史定位报告\n\n入口位于 `src/app.py`。")
        first_result = pipeline(data, connection, tasks, repository, first_discovery).run(
            first["runs"][0]["id"]
        )
        assert first_result.status == "completed"
        assert "Similar historical localization report" not in first_discovery.entry

        second = tasks.ingest(
            IngestedTicket(
                "tapd",
                "1251357",
                "【v4.8、trunk】【一键养成-目标设定】选择另一个目标时没有二次确认框",
                {"description": "缺少二次确认"},
            ),
            "lua",
            "automatic",
        )
        second_discovery = Discovery("# 当前定位报告\n\n重新核对当前代码。")
        second_result = pipeline(data, connection, tasks, repository, second_discovery).run(
            second["runs"][0]["id"]
        )

        assert second_result.status == "completed"
        assert "Similar historical localization report" in second_discovery.entry
        assert "1253280" in second_discovery.entry
        assert "共同功能模块“一键养成”" in second_discovery.entry
