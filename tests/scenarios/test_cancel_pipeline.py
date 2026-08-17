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
def git(cwd:Path,*args:str)->str:return subprocess.run(["git",*args],cwd=cwd,check=True,text=True,capture_output=True).stdout.strip()

class Discovery:
    runtime_name="fake"
    def __init__(self,revision:str):self.revision=revision
    def run(self,request):
        return AgentRunResult(status="succeeded",exit_code=0,session_id="d",structured_output=None,final_text="# 定位报告\n\n目标位于 `src/app.py`。")
class CancelingRepair:
    runtime_name="fake"
    def __init__(self,tasks:TaskStore,task_id:str):self.tasks=tasks;self.task_id=task_id
    def run(self,request):
        self.tasks.cancel_task(self.task_id);(request.cwd/"src/app.py").write_text("def get_value():\n    return 2\n",encoding="utf-8")
        return AgentRunResult(status="succeeded",exit_code=0,session_id="r",structured_output={"schema_version":1,"outcome":"changed","summary":"Would have changed the value.","changed_paths_claimed":["src/app.py"],"checks_requested":[],"limitations":[]})
def test_cancel_during_repair_never_freezes_or_delivers(tmp_path:Path):
    repo=tmp_path/"repo";repo.mkdir();(repo/"src").mkdir();git(repo,"init");git(repo,"config","user.email","test@codefixer.local");git(repo,"config","user.name","Test");(repo/"src/app.py").write_text("def get_value():\n    return 1\n",encoding="utf-8");git(repo,"add", ".");git(repo,"commit","-m","base");revision=git(repo,"rev-parse","HEAD")
    data=tmp_path/"data";data.mkdir()
    with connect_database(data/"codefixer.db") as connection:
        apply_migrations(connection);tasks=TaskStore(connection);task=tasks.ingest(IngestedTicket("fake","BUG-CANCEL","Cancel me",{"description":"wrong"}),"project-a","automatic");run_id=task["runs"][0]["id"]
        source=GitSourceAdapter(repo,["git"]);pipeline=ChangedPipeline(tasks=tasks,artifacts=ArtifactStore(data,SchemaRegistry(ROOT/"contracts")),artifact_index=ArtifactIndex(connection,data),source=source,localization_source=DirectReadOnlySourceAdapter(repo,source.current_revision,source_type="git"),discovery_agent=Discovery(revision),repair_agent=CancelingRepair(tasks,task["id"]),verification_runner=VerificationRunner(),verification_steps=(),project={"id":"project-a","localizationSource":{"id":"project-source","type":"git","path":str(repo)},"modificationWorkspace":{"id":"project-source","path":str(repo),"vcsKind":"git","allowedRoots":["src"],"allowedExtensions":[".py"]}},source_policy=SourcePolicy(allowed_roots=("src",),allowed_extensions=(".py",)),delivery=DeliveryCoordinator((PatchFinalAction(action_id="primary-patch",action_version=1,store=DeliveryStore(connection),output_directory=data/"patches"),)))
        result=pipeline.run(run_id);assert result.status=="canceled";detail=tasks.get_task(task["id"]);assert detail["status"]=="canceled";assert not (data/"patches").exists();assert not (data/"tasks"/task["id"]/"runs"/run_id/"freeze-change").exists();assert git(repo,"status","--porcelain")==""
