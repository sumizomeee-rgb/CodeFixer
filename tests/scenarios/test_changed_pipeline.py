from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from codefixer.adapters.delivery_patch import PatchFinalAction
from codefixer.adapters.sources.directory import DirectReadOnlySourceAdapter
from codefixer.adapters.sources.git import GitSourceAdapter
from codefixer.application.ports.agents import AgentRunResult
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

ROOT = Path(__file__).resolve().parents[2]


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True).stdout.strip()


class DiscoveryAgent:
    runtime_name = "fake"
    def __init__(self):
        self.entry = ""
    def run(self, request):
        assert request.cwd.name == "repo"
        self.entry = request.entry_file.read_text(encoding="utf-8")
        return AgentRunResult(status="succeeded", exit_code=0, session_id="d1", structured_output=None, final_text="# 定位报告\n\n根因位于 `src/app.py::get_value`。")


class RepairAgent:
    runtime_name = "fake"
    def run(self, request):
        (request.cwd / "src/app.py").write_text("def get_value():\n    return 2\n", encoding="utf-8")
        return AgentRunResult(status="succeeded", exit_code=0, session_id="r1", structured_output={"schema_version":1,"outcome":"changed","summary":"Return the corrected value.","module_name":"app","change_summary":"修正返回值","changed_paths_claimed":["src/app.py"],"checks_requested":["compile"],"limitations":[],"blocking_code":None,"blocking_evidence_ids":[]})


def _entry_paths(entry: Path):
    result=[]
    for line in entry.read_text(encoding="utf-8").splitlines():
        if line.startswith("- ") and ": `" in line:
            label,raw=line[2:].split(": `",1);result.append((label,Path(raw.rstrip("`"))))
    return result


def test_normal_changed_patch_journey(tmp_path: Path):
    repo=tmp_path/"repo";repo.mkdir();(repo/"src").mkdir();git(repo,"init");git(repo,"config","user.email","test@codefixer.local");git(repo,"config","user.name","Test")
    (repo/"src/app.py").write_text("def get_value():\n    return 1\n",encoding="utf-8");git(repo,"add", ".");git(repo,"commit","-m","base");revision=git(repo,"rev-parse","HEAD")
    data=tmp_path/"data";data.mkdir();db=data/"codefixer.db"
    with connect_database(db) as connection:
        apply_migrations(connection);tasks=TaskStore(connection);task=tasks.ingest(IngestedTicket("fake","BUG-1","Wrong value",{"description":"get_value returns 1"}),"project-a","automatic");run_id=task["runs"][0]["id"]
        source=GitSourceAdapter(repo,["git"]);discovery_agent=DiscoveryAgent();pipeline=ChangedPipeline(tasks=tasks,artifacts=ArtifactStore(data,SchemaRegistry(ROOT/"contracts")),artifact_index=ArtifactIndex(connection,data),source=source,localization_source=DirectReadOnlySourceAdapter(repo,source.current_revision,source_type="git"),discovery_agent=discovery_agent,repair_agent=RepairAgent(),verification_runner=VerificationRunner(),verification_steps=(VerificationStep("compile",("python","-m","py_compile","src/app.py")),),project={"id":"project-a","localizationPrompt":"优先检查 Lua 服务注册表。","localizationSource":{"id":"project-source","type":"git","path":str(repo)},"modificationWorkspace":{"id":"project-source","path":str(repo),"vcsKind":"git","allowedRoots":["src"],"allowedExtensions":[".py"]}},source_policy=SourcePolicy(allowed_roots=("src",),allowed_extensions=(".py",)),delivery=DeliveryCoordinator((PatchFinalAction(action_id="primary-patch",action_version=1,store=DeliveryStore(connection),output_directory=data/"patches"),)))
        result=pipeline.run(run_id);assert result.status=="completed" and result.result=="changed";assert result.deliveries and result.deliveries[0].succeeded
        detail=tasks.get_task(task["id"]);assert detail["status"]=="completed" and detail["result"]=="changed";assert len(list((data/"patches").glob("*.patch")))==1
        discovery_root=data/"tasks"/task["id"]/"runs"/run_id/"stages/discovery";assert "src/app.py" in (discovery_root/"localization-report.md").read_text(encoding="utf-8");assert json.loads((discovery_root/"agent-runtime.json").read_text())["session_id"]=="d1"
        assert "优先检查 Lua 服务注册表。" in discovery_agent.entry
        manifest_path=data/"tasks"/task["id"]/"runs"/run_id/"freeze-change/change-manifest.json";manifest=json.loads(manifest_path.read_text());assert manifest["modification_source"]["base_revision"]==revision;assert manifest["files"][0]["path"]=="src/app.py"
        frozen_file=manifest_path.parent/"files/src/app.py";assert frozen_file.read_text(encoding="utf-8")=="def get_value():\n    return 2\n";assert hashlib.sha256(frozen_file.read_bytes()).hexdigest()==manifest["files"][0]["content_sha256"];assert git(repo,"status","--porcelain")==""
