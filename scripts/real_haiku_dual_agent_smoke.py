#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from codefixer.adapters.agents import build_agent_runtime
from codefixer.adapters.delivery_patch import PatchFinalAction
from codefixer.adapters.sources.git import GitSourceAdapter
from codefixer.application.ports.sources import SourcePolicy
from codefixer.application.services.delivery import DeliveryCoordinator
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

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "docs" / "testing" / "reports" / "real-haiku-dual-agent-2026-08-13"


def run(command: list[str], cwd: Path) -> str:
    return subprocess.run(command, cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


def main() -> int:
    if REPORT_ROOT.exists():
        raise SystemExit(f"report already exists: {REPORT_ROOT}")
    with tempfile.TemporaryDirectory(prefix="codefixer-haiku-smoke-") as raw_temp:
        temp = Path(raw_temp)
        repo = temp / "demo-repo"
        repo.mkdir()
        (repo / "src").mkdir()
        (repo / "tests").mkdir()
        (repo / "src" / "clamp.py").write_text(
            "def clamp_percent(value: int) -> int:\n    return min(0, max(100, value))\n",
            encoding="utf-8",
        )
        (repo / "tests" / "test_clamp.py").write_text(
            "from src.clamp import clamp_percent\n\n"
            "def test_clamp_percent():\n"
            "    assert clamp_percent(-5) == 0\n"
            "    assert clamp_percent(40) == 40\n"
            "    assert clamp_percent(130) == 100\n",
            encoding="utf-8",
        )
        run(["git", "init"], repo)
        run(["git", "config", "user.email", "smoke@codefixer.local"], repo)
        run(["git", "config", "user.name", "CodeFixer Smoke"], repo)
        run(["git", "add", "."], repo)
        run(["git", "commit", "-m", "seed controlled bug"], repo)
        revision = run(["git", "rev-parse", "HEAD"], repo)

        data = temp / "data"
        data.mkdir()
        profile = {
            "id": "claude-haiku-smoke",
            "runtime": "claudeCode",
            "executableRef": "claude-code-cli",
            "model": "haiku",
            "timeoutSeconds": 900,
            "maxBudgetUsd": 2,
        }
        runtime = build_agent_runtime(profile, {"claude-code-cli": {"command": ["claude"]}})
        project = {
            "id": "controlled-haiku-demo",
            "localizationSource": {"id": "localization-source", "type": "repository", "path": str(repo)},
            "modificationWorkspace": {"id": "modification-workspace", "path": str(repo), "vcsKind": "git"},
            "finalActions": [{"id": "patch-only", "type": "patch"}],
        }
        # sqlite3.Connection 的上下文管理器只提交事务，并不会关闭文件句柄。
        # 真实验收结束时显式关闭，确保 Windows 临时目录可以完整清理。
        with closing(connect_database(data / "codefixer.db")) as connection:
            apply_migrations(connection)
            tasks = TaskStore(connection)
            task = tasks.ingest(
                IngestedTicket(
                    "fake-haiku",
                    "FAKE-HAIKU-001",
                    "clamp_percent returns the wrong boundary",
                    {
                        "description": (
                            "clamp_percent should return 0 below zero, preserve values from 0 through 100, "
                            "and return 100 above 100. The controlled repository tests describe the expected behavior."
                        )
                    },
                    "v1",
                    True,
                ),
                str(project["id"]),
                "automatic",
            )
            run_id = task["runs"][0]["id"]
            pipeline = ChangedPipeline(
                tasks=tasks,
                artifacts=ArtifactStore(data, SchemaRegistry(ROOT / "contracts")),
                artifact_index=ArtifactIndex(connection, data),
                source=GitSourceAdapter(repo, ["git"]),
                scope_discovery_agent=runtime,
                discovery_agent=runtime,
                repair_agent=runtime,
                review_agent=runtime,
                verification_runner=VerificationRunner(),
                verification_steps=(
                    VerificationStep("pytest", (sys.executable, "-m", "pytest", "-q"), timeout_seconds=120),
                ),
                project=project,
                source_policy=SourcePolicy(allowed_roots=("src",), allowed_extensions=(".py",)),
                delivery=DeliveryCoordinator(
                    (
                        PatchFinalAction(
                            action_id="patch-only",
                            action_version=1,
                            store=DeliveryStore(connection),
                            output_directory=data / "patches",
                        ),
                    )
                ),
                max_repair_attempts=1,
            )
            result = pipeline.run(run_id)
            detail = tasks.get_task(task["id"])
            run_root = data / "tasks" / task["id"] / "runs" / run_id
            REPORT_ROOT.mkdir(parents=True)
            shutil.copytree(run_root / "stages", REPORT_ROOT / "stages")
            patches = list((data / "patches").glob("*.patch")) if (data / "patches").exists() else []
            if patches:
                shutil.copy2(patches[0], REPORT_ROOT / "change.patch")
            sessions: dict[str, str | None] = {}
            durations: dict[str, float] = {}
            for stage in ("scope_discovery", "discovery", "repair", "review"):
                diagnostics = list((run_root / "stages" / stage).rglob("agent-runtime.json"))
                if not diagnostics:
                    sessions[stage] = None
                    durations[stage] = 0
                    continue
                diagnostic = json.loads(diagnostics[-1].read_text(encoding="utf-8"))
                sessions[stage] = diagnostic.get("session_id")
                durations[stage] = float(diagnostic.get("duration_seconds") or 0)
            report = {
                "task_id": task["id"],
                "run_id": run_id,
                "status": result.status,
                "result": result.result,
                "failure": detail.get("failure"),
                "source_revision": revision,
                "sessions": sessions,
                "durations_seconds": durations,
                "patch_count": len(patches),
                "original_repo_status": run(["git", "status", "--porcelain"], repo),
            }
            (REPORT_ROOT / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (REPORT_ROOT / "README.md").write_text(
                "# Claude Haiku 双 Agent 真实验收\n\n"
                f"- 状态：`{result.status} / {result.result}`\n"
                f"- Scope session：`{sessions['scope_discovery']}`\n"
                f"- Discovery session：`{sessions['discovery']}`\n"
                f"- Repair session：`{sessions['repair']}`\n"
                f"- Review session：`{sessions['review']}`\n"
                f"- Patch 数量：`{len(patches)}`\n"
                f"- 原始仓库状态：`{report['original_repo_status'] or 'clean'}`\n",
                encoding="utf-8",
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            unique_sessions = {value for value in sessions.values() if value is not None}
            if result.status != "completed" or result.result != "changed" or len(unique_sessions) != 4:
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
