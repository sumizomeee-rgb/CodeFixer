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

def git(cwd: Path, *args: str) -> str: return subprocess.run(["git",*args],cwd=cwd,check=True,text=True,capture_output=True).stdout.strip()

class DiscoveryNoChange:
    runtime_name="fake"
    def run(self,request):
        return AgentRunResult(status="succeeded",exit_code=0,session_id="d",structured_output=None,final_text="# 定位报告\n\n当前实现可能已经满足工单。")
class NoChangeCoder:
    runtime_name="fake"
    def run(self,request):
        return AgentRunResult(status="succeeded",exit_code=0,session_id="n",structured_output={"schema_version":1,"outcome":"no_valid_diff","summary":"当前代码已满足工单。","module_name":None,"change_summary":None,"changed_paths_claimed":[],"checks_requested":[],"limitations":[],"blocking_code":None,"blocking_evidence_ids":[]})

def test_no_change_is_a_healthy_reviewed_terminal_result(tmp_path:Path):
    repo=tmp_path/'repo';repo.mkdir();(repo/'src').mkdir();git(repo,'init');git(repo,'config','user.email','test@codefixer.local');git(repo,'config','user.name','Test');(repo/'src/app.py').write_text('def get_value():\n    return 2\n',encoding='utf-8');git(repo,'add','.');git(repo,'commit','-m','already fixed')
    data=tmp_path/'data';data.mkdir()
    with connect_database(data/'codefixer.db') as connection:
        apply_migrations(connection);tasks=TaskStore(connection);task=tasks.ingest(IngestedTicket('fake','BUG-2','Old report',{'description':'returns 1'}),'project-a','automatic');run_id=task['runs'][0]['id']
        source=GitSourceAdapter(repo,['git']);pipeline=ChangedPipeline(tasks=tasks,artifacts=ArtifactStore(data,SchemaRegistry(ROOT/'contracts')),artifact_index=ArtifactIndex(connection,data),source=source,localization_source=DirectReadOnlySourceAdapter(repo,source.current_revision,source_type='git'),discovery_agent=DiscoveryNoChange(),repair_agent=NoChangeCoder(),verification_runner=VerificationRunner(),verification_steps=(),project={'id':'project-a','localizationSource':{'id':'project-source','type':'git','path':str(repo)},'modificationWorkspace':{'id':'project-source','path':str(repo),'vcsKind':'git','allowedRoots':['src']}},source_policy=SourcePolicy(allowed_roots=('src',)),delivery=DeliveryCoordinator((PatchFinalAction(action_id='primary-patch',action_version=1,store=DeliveryStore(connection),output_directory=data/'patches'),)))
        result=pipeline.run(run_id);assert result.status=='completed' and result.result=='no_change';assert not (data/'patches').exists();detail=tasks.get_task(task['id']);assert detail['status']=='completed' and detail['result']=='no_change';assert git(repo,'status','--porcelain')==''
