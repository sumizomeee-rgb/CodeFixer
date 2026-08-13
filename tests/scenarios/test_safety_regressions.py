from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from codefixer.adapters.delivery_patch import PatchFinalAction
from codefixer.adapters.sources.git import GitSourceAdapter
from codefixer.application.ports.agents import AgentRunResult
from codefixer.application.ports.sources import SourcePolicy
from codefixer.application.services.delivery import DeliveryCoordinator
from codefixer.application.services.stability import PreDeliveryStabilityGuard
from codefixer.application.services.verification import VerificationRunner, VerificationStep
from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.artifact_index import ArtifactIndex
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.delivery_store import DeliveryStore
from codefixer.infrastructure.task_store import TaskStore
from codefixer.orchestration import ChangedPipeline
from codefixer.protocols import ArtifactStore, SchemaRegistry

ROOT = Path(__file__).resolve().parents[2]
def git(cwd:Path,*args:str)->str:return subprocess.run(["git",*args],cwd=cwd,check=True,text=True,capture_output=True).stdout.strip()
def repo(tmp_path:Path)->tuple[Path,str]:
    root=tmp_path/"repo";root.mkdir();(root/"src").mkdir();(root/"src/app.py").write_text("def get_value():\n    return 1\n",encoding="utf-8");(root/"README.md").write_text("safe\n",encoding="utf-8");git(root,"init");git(root,"config","user.email","test@codefixer.local");git(root,"config","user.name","Test");git(root,"add", ".");git(root,"commit","-m","base");return root,git(root,"rev-parse","HEAD")
class Discovery:
    runtime_name="fake"
    def __init__(self,revision:str):self.revision=revision
    def run(self,request):return AgentRunResult(status="succeeded",exit_code=0,session_id="discovery",structured_output={"schema_version":1,"decision":"located","source":{"id":"project-source","revision":self.revision},"summary":"Target is src/app.py.","candidate_scope":["src/app.py"],"evidence":[{"id":"ev-source","kind":"source","location":"src/app.py","revision":self.revision,"locator":"get_value","summary":"Current implementation returns the stale value.","content_sha256":None}],"failure":None})
class ScopeDiscovery:
    runtime_name="fake"
    def __init__(self,revision:str):self.revision=revision
    def run(self,request):return AgentRunResult(status="succeeded",exit_code=0,session_id="scope",structured_output={"schema_version":1,"outcome":"candidates","source":{"id":"project-source","revision":self.revision},"summary":"Likely target.","candidate_scope":["src/app.py"],"search_entry_points":["Search get_value"],"limitations":[],"failure":None})
class UnresolvedScope:
    runtime_name="fake"
    def __init__(self,revision:str):self.revision=revision
    def run(self,request):return AgentRunResult(status="succeeded",exit_code=0,session_id="scope-unresolved",structured_output={"schema_version":1,"outcome":"unresolved","source":{"id":"project-source","revision":self.revision},"summary":"No reliable source clue.","candidate_scope":[],"search_entry_points":[],"limitations":["Ticket has no symbols or paths."],"failure":{"code":"insufficient_clues","summary":"The ticket cannot be mapped to source.","retryable":False}})
class RepairSequence:
    runtime_name="fake"
    def __init__(self,*,unauthorized:bool=False):self.calls=0;self.unauthorized=unauthorized
    def run(self,request):
        self.calls+=1;value=2 if self.calls==1 else 3;(request.cwd/"src/app.py").write_text(f"def get_value():\n    return {value}\n",encoding="utf-8");claimed=["src/app.py"]
        if self.unauthorized:(request.cwd/"README.md").write_text("mutated\n",encoding="utf-8");claimed.append("README.md")
        return AgentRunResult(status="succeeded",exit_code=0,session_id=f"repair-{self.calls}",structured_output={"schema_version":1,"outcome":"changed","summary":"Update the stale value.","changed_paths_claimed":claimed,"checks_requested":["compile"],"limitations":[]})
def entry_path(entry:Path,label:str)->Path:
    for line in entry.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"- {label}: `"):return Path(line.split(": `",1)[1].rstrip("`"))
    raise AssertionError(f"missing {label}")
class ReviewSequence:
    runtime_name="fake"
    def __init__(self,verdicts:list[str]):self.verdicts=verdicts;self.calls=0
    def run(self,request):
        patch=entry_path(request.entry_file,"Candidate diff");digest=hashlib.sha256(patch.read_bytes()).hexdigest();verdict=self.verdicts[min(self.calls,len(self.verdicts)-1)];self.calls+=1
        return AgentRunResult(status="succeeded",exit_code=0,session_id=f"review-{self.calls}",structured_output={"schema_version":1,"mode":"change","input_sha256":digest,"verdict":verdict,"summary":"Needs one more repair." if verdict=="needs_repair" else "Approved.","issues":[] if verdict=="approved" else [{"severity":"blocking","summary":"Use the final value.","evidence_ids":[]}]})
class NeverReview:
    runtime_name="fake"
    def run(self,request):raise AssertionError("review must not run after unauthorized modification")
class LatestTicketProvider:
    def __init__(self,latest:IngestedTicket):self.latest=latest
    def fetch(self,external_ticket_id:str)->IngestedTicket:assert external_ticket_id==self.latest.external_ticket_id;return self.latest
class StableSourceView:
    def __init__(self,source:GitSourceAdapter):self.source=source
    def current_revision(self)->str:return self.source.current_revision()
def build_pipeline(*,tmp_path:Path,tasks:TaskStore,connection,source:GitSourceAdapter,revision:str,repair,review,scope=None,stability_guard=None)->ChangedPipeline:
    data=tmp_path/"data";repository=source.repository_path;return ChangedPipeline(tasks=tasks,artifacts=ArtifactStore(data,SchemaRegistry(ROOT/"contracts")),artifact_index=ArtifactIndex(connection,data),source=source,scope_discovery_agent=scope or ScopeDiscovery(revision),discovery_agent=Discovery(revision),repair_agent=repair,review_agent=review,verification_runner=VerificationRunner(),verification_steps=(VerificationStep("compile",("python","-m","py_compile","src/app.py")),),project={"id":"project-a","localizationSource":{"id":"project-source","type":"git","path":str(repository)},"modificationWorkspace":{"id":"project-source","path":str(repository),"vcsKind":"git","allowedRoots":["src"],"allowedExtensions":[".py"]}},source_policy=SourcePolicy(allowed_roots=("src",),allowed_extensions=(".py",)),delivery=DeliveryCoordinator((PatchFinalAction(action_id="primary-patch",action_version=1,store=DeliveryStore(connection),output_directory=data/"patches"),)),max_repair_attempts=3,stability_guard=stability_guard)
def ingest(tasks:TaskStore,ticket:IngestedTicket)->tuple[dict,str]:task=tasks.ingest(ticket,"project-a","automatic");return task,task["runs"][0]["id"]
def test_review_needs_repair_loops_then_freezes_only_approved_candidate(tmp_path:Path):
    repository,revision=repo(tmp_path);data=tmp_path/"data";data.mkdir()
    with connect_database(data/"codefixer.db") as connection:
        apply_migrations(connection);tasks=TaskStore(connection);task,run_id=ingest(tasks,IngestedTicket("fake","BUG-LOOP","Loop",{"description":"wrong"},"v1",True));repair=RepairSequence();review=ReviewSequence(["needs_repair","approved"]);result=build_pipeline(tmp_path=tmp_path,tasks=tasks,connection=connection,source=GitSourceAdapter(repository,["git"]),revision=revision,repair=repair,review=review).run(run_id);assert result.status=="completed" and result.result=="changed";assert repair.calls==2 and review.calls==2;frozen=data/"tasks"/task["id"]/"runs"/run_id/"freeze-change/files/src/app.py";assert "return 3" in frozen.read_text(encoding="utf-8");assert git(repository,"status","--porcelain")==""
def test_unauthorized_path_fails_before_verification_review_or_delivery(tmp_path:Path):
    repository,revision=repo(tmp_path);data=tmp_path/"data";data.mkdir()
    with connect_database(data/"codefixer.db") as connection:
        apply_migrations(connection);tasks=TaskStore(connection);task,run_id=ingest(tasks,IngestedTicket("fake","BUG-SCOPE","Scope",{"description":"wrong"},"v1",True));result=build_pipeline(tmp_path=tmp_path,tasks=tasks,connection=connection,source=GitSourceAdapter(repository,["git"]),revision=revision,repair=RepairSequence(unauthorized=True),review=NeverReview()).run(run_id);assert result.status=="failed";detail=tasks.get_task(task["id"]);assert detail["failure"]["code"]=="unauthorized_change";assert not (data/"patches").exists();assert not (data/"tasks"/task["id"]/"runs"/run_id/"freeze-change").exists();assert git(repository,"status","--porcelain")==""
def test_ticket_change_after_review_blocks_freeze_and_delivery(tmp_path:Path):
    repository,revision=repo(tmp_path);source=GitSourceAdapter(repository,["git"]);data=tmp_path/"data";data.mkdir();frozen=IngestedTicket("fake","BUG-STALE","Stale",{"description":"original"},"v1",True);latest=IngestedTicket("fake","BUG-STALE","Stale",{"description":"changed while running"},"v2",True);guard=PreDeliveryStabilityGuard(LatestTicketProvider(latest),StableSourceView(source))
    with connect_database(data/"codefixer.db") as connection:
        apply_migrations(connection);tasks=TaskStore(connection);task,run_id=ingest(tasks,frozen);result=build_pipeline(tmp_path=tmp_path,tasks=tasks,connection=connection,source=source,revision=revision,repair=RepairSequence(),review=ReviewSequence(["approved"]),stability_guard=guard).run(run_id);assert result.status=="failed";detail=tasks.get_task(task["id"]);assert detail["failure"]["code"]=="ticket_changed_during_run";assert not (data/"patches").exists();assert not (data/"tasks"/task["id"]/"runs"/run_id/"freeze-change").exists();assert git(repository,"status","--porcelain")==""
def test_unresolved_scope_marks_stage_and_task_failed_with_reason(tmp_path:Path):
    repository,revision=repo(tmp_path);data=tmp_path/"data";data.mkdir()
    with connect_database(data/"codefixer.db") as connection:
        apply_migrations(connection);tasks=TaskStore(connection);task,run_id=ingest(tasks,IngestedTicket("fake","BUG-NO-SCOPE","Unknown",{"description":"no source clues"},"v1",True));result=build_pipeline(tmp_path=tmp_path,tasks=tasks,connection=connection,source=GitSourceAdapter(repository,["git"]),revision=revision,repair=NeverReview(),review=NeverReview(),scope=UnresolvedScope(revision)).run(run_id);assert result.status=="failed";detail=tasks.get_task(task["id"]);assert detail["failure"]["code"]=="scope_discovery_failed";scope_stage=next(stage for stage in detail["runs"][0]["stages"] if stage["stage_id"]=="scope_discovery");assert scope_stage["status"]=="failed";assert scope_stage["failure"]["summary"]=="The ticket cannot be mapped to source."
