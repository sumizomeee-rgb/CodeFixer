from __future__ import annotations

from pathlib import Path

from codefixer.adapters.delivery.gitlab import GitLabMrDelivery, MergeRequestRef
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.delivery_store import DeliveryStore


class FakeMaterializer:
    def __init__(self): self.materialize_calls=0
    def refresh(self): pass
    def commit_exists(self, commit): return commit == "delivery-commit"
    def create_delivery_commit(self, **kwargs): return "delivery-commit"
    def materialize_target(self, **kwargs):
        self.materialize_calls += 1
        class Result: target_commit = "target-commit"
        return Result()


class CrashThenRecoverGitLab:
    def __init__(self): self.mr=None; self.create_calls=0; self.crash=False; self.branch_commit=None
    def get_branch_commit(self, project_id, branch): return self.branch_commit
    def find_merge_request(self, project_id, source_branch, target_branch): return self.mr
    def create_merge_request(self, project_id, *, source_branch, target_branch, title, description):
        self.create_calls += 1
        self.mr = MergeRequestRef("42", "https://gitlab/mr/42", "opened", source_branch, target_branch)
        if self.crash: raise RuntimeError("process died after remote create")
        return self.mr


def seed_run(connection):
    connection.execute("INSERT INTO ticket_records(provider_instance_id,external_ticket_id,title) VALUES ('p','1','t')")
    connection.execute("INSERT INTO tasks(id,ticket_record_id,project_id,status) VALUES ('task',1,'project','running')")
    connection.execute("INSERT INTO task_runs(id,task_id,status,execution_mode_snapshot) VALUES ('run','task','running','automatic')")
    connection.commit()


def test_restart_reconciles_remote_mr_without_duplicate_create(tmp_path: Path):
    data=tmp_path/"data";data.mkdir();patch=tmp_path/"change.patch";patch.write_text("diff\n")
    with connect_database(data/"db.sqlite") as connection:
        apply_migrations(connection);seed_run(connection);store=DeliveryStore(connection);remote=CrashThenRecoverGitLab();materializer=FakeMaterializer();delivery=GitLabMrDelivery(store,remote,materializer)
        remote.crash=True
        try: delivery.deliver(task_id="task",run_id="run",action_id="mr",action_version=1,project_id=1,config={"targetBranches":["main"]},frozen_patch=patch,base_revision="base",target_branches=("main",),work_root=tmp_path/"work",title="Fix",description="d")
        except RuntimeError: pass
        assert remote.create_calls==1 and remote.mr is not None
        remote.crash=False
        results=delivery.deliver(task_id="task",run_id="run",action_id="mr",action_version=1,project_id=1,config={"targetBranches":["main"]},frozen_patch=patch,base_revision="base",target_branches=("main",),work_root=tmp_path/"work2",title="Fix",description="d")
        assert remote.create_calls==1 and results[0].adopted_existing;action=store.get_action(1);assert action["status"]=="succeeded" and action["targets"][0]["external_id"]=="42"


class PartialMaterializer(FakeMaterializer):
    def materialize_target(self, **kwargs):
        if kwargs["target_branch"] == "release/bad":
            from codefixer.adapters.sources.common import SourceCommandError
            raise SourceCommandError("cherry-pick conflict")
        return super().materialize_target(**kwargs)


class RecordingGitLab(CrashThenRecoverGitLab):
    def __init__(self): super().__init__(); self.mrs = {}
    def find_merge_request(self, project_id, source_branch, target_branch): return self.mrs.get((source_branch,target_branch))
    def create_merge_request(self, project_id, *, source_branch, target_branch, title, description):
        self.create_calls += 1; mr=MergeRequestRef(str(self.create_calls),f"https://gitlab/mr/{self.create_calls}","opened",source_branch,target_branch);self.mrs[(source_branch,target_branch)]=mr;return mr


def test_one_target_conflict_does_not_hide_other_target_success(tmp_path: Path):
    data=tmp_path/"data";data.mkdir();patch=tmp_path/"change.patch";patch.write_text("diff\n")
    with connect_database(data/"db.sqlite") as connection:
        apply_migrations(connection);seed_run(connection);store=DeliveryStore(connection);remote=RecordingGitLab();delivery=GitLabMrDelivery(store,remote,PartialMaterializer())
        results=delivery.deliver(task_id="task",run_id="run",action_id="mr",action_version=1,project_id=1,config={"targetBranches":["release/bad","main"]},frozen_patch=patch,base_revision="base",target_branches=("release/bad","main"),work_root=tmp_path/"work",title="Fix",description="d")
        assert [item.target_branch for item in results]==["main"];action=store.get_action(1);assert action["status"]=="failed" and action["outcome"]=="partial_success";targets={item["target_key"]:item for item in action["targets"]};assert targets["release/bad"]["status"]=="failed" and targets["main"]["status"]=="succeeded"
