from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from codefixer.adapters.delivery_patch import PatchFinalAction
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

def git(cwd: Path, *args: str) -> str: return subprocess.run(["git",*args],cwd=cwd,check=True,text=True,capture_output=True).stdout.strip()

class ScopeDiscovery:
    runtime_name="fake"
    def __init__(self,revision:str):self.revision=revision
    def run(self,request):return AgentRunResult(status="succeeded",exit_code=0,session_id="s",structured_output={"schema_version":1,"outcome":"candidates","source":{"id":"project-source","revision":self.revision},"summary":"Inspect the current value and history.","candidate_scope":["src/app.py"],"search_entry_points":["Read get_value and git history"],"limitations":[],"failure":None})

class DiscoveryNoChange:
    runtime_name="fake"
    def __init__(self,revision:str):self.revision=revision
    def run(self,request):
        return AgentRunResult(status="succeeded",exit_code=0,session_id="d",structured_output={"schema_version":1,"decision":"no_change_claim","source":{"id":"project-source","revision":self.revision},"summary":"Current baseline already returns the corrected value.","candidate_scope":[],"evidence":[{"id":"ev-1","kind":"source","location":"src/app.py","revision":self.revision,"locator":"get_value","summary":"Current baseline returns 2.","content_sha256":None},{"id":"ev-2","kind":"history","location":"git log","revision":self.revision,"locator":"HEAD","summary":"Fix commit is present in baseline.","content_sha256":None}],"failure":None})
class NoChangeVerifier:
    runtime_name="fake"
    def __init__(self,revision:str):self.revision=revision
    def run(self,request):
        return AgentRunResult(status="succeeded",exit_code=0,session_id="n",structured_output={"schema_version":1,"reason":"already_fixed","source":{"id":"project-source","revision":self.revision},"claim":"The frozen baseline contains the correction and needs no delivery.","evidence":[{"id":"ev-1","kind":"source","location":"src/app.py","revision":self.revision,"locator":"get_value","summary":"Current code returns 2.","content_sha256":None},{"id":"ev-2","kind":"history","location":"git log","revision":self.revision,"locator":"HEAD","summary":"Historical fix is in the baseline.","content_sha256":None}],"limitations":[]})
class NoChangeReview:
    runtime_name="fake"
    def run(self,request):
        report_path=None
        for line in request.entry_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("- No-change report: `"):report_path=Path(line.split("`",1)[1].rstrip("`"))
        assert report_path is not None;digest=hashlib.sha256(report_path.read_bytes()).hexdigest()
        return AgentRunResult(status="succeeded",exit_code=0,session_id="v",structured_output={"schema_version":1,"mode":"no_change","input_sha256":digest,"verdict":"approved","summary":"Positive evidence is sufficient.","issues":[]})

def test_no_change_is_a_healthy_reviewed_terminal_result(tmp_path:Path):
    repo=tmp_path/'repo';repo.mkdir();(repo/'src').mkdir();git(repo,'init');git(repo,'config','user.email','test@codefixer.local');git(repo,'config','user.name','Test');(repo/'src/app.py').write_text('def get_value():\n    return 2\n',encoding='utf-8');git(repo,'add','.');git(repo,'commit','-m','already fixed');revision=git(repo,'rev-parse','HEAD')
    data=tmp_path/'data';data.mkdir()
    with connect_database(data/'codefixer.db') as connection:
        apply_migrations(connection);tasks=TaskStore(connection);task=tasks.ingest(IngestedTicket('fake','BUG-2','Old report',{'description':'returns 1'}),'project-a','automatic');run_id=task['runs'][0]['id']
        pipeline=ChangedPipeline(tasks=tasks,artifacts=ArtifactStore(data,SchemaRegistry(ROOT/'contracts')),artifact_index=ArtifactIndex(connection,data),source=GitSourceAdapter(repo,['git']),scope_discovery_agent=ScopeDiscovery(revision),discovery_agent=DiscoveryNoChange(revision),repair_agent=NoChangeVerifier(revision),review_agent=NoChangeReview(),verification_runner=VerificationRunner(),verification_steps=(),project={'id':'project-a','modificationSource':{'id':'project-source','type':'git','repositoryRef':'repo'}},source_policy=SourcePolicy(allowed_roots=('src',)),delivery=DeliveryCoordinator((PatchFinalAction(action_id='primary-patch',action_version=1,store=DeliveryStore(connection),output_directory=data/'patches'),)))
        result=pipeline.run(run_id);assert result.status=='completed' and result.result=='no_change';assert not (data/'patches').exists();detail=tasks.get_task(task['id']);assert detail['status']=='completed' and detail['result']=='no_change';assert git(repo,'status','--porcelain')==''
