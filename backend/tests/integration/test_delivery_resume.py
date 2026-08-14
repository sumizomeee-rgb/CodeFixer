from __future__ import annotations

import hashlib
import json
from pathlib import Path

from codefixer.config import load_config
from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.config_store import ConfigStore
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.task_store import TaskStore
from codefixer.orchestration.factory import RunExecutor
from codefixer.orchestration.recovery import RecoveryService


def _config(tmp_path: Path) -> tuple[Path, dict[str, object]]:
    config_path=tmp_path/"config/defaults/codefixer.json";config_path.parent.mkdir(parents=True);project={"id":"demo","name":"Demo","deliveryLog":{"technologyTag":"Python","submitterName":"Tester"},"finalActions":[{"id":"primary-patch","type":"patch","outputDirectory":str((tmp_path/"data/patches").resolve())}]}
    config_path.write_text(json.dumps({"schemaVersion":1,"server":{"host":"127.0.0.1","port":9522},"storage":{"dataRoot":"../../data"},"execution":{"mode":"automatic","maxConcurrentTasks":1,"maxRepairAttempts":3},"ticketProviders":[],"agentProfiles":[],"knowledgeProviders":[],"executableBindings":{},"projects":[project]},indent=2),encoding="utf-8")
    return config_path,project


def test_frozen_patch_delivery_resumes_after_restart_without_duplicate_output(tmp_path: Path):
    config_path,project=_config(tmp_path);loaded=load_config(config_path);loaded.data_root.mkdir(parents=True);patch_text="diff --git a/app.txt b/app.txt\n--- a/app.txt\n+++ b/app.txt\n@@ -1 +1 @@\n-old\n+new\n";patch_sha=hashlib.sha256(patch_text.encode()).hexdigest();contracts_root=Path(__file__).resolve().parents[3]/"contracts"
    with connect_database(loaded.data_root/"codefixer.db") as connection:
        apply_migrations(connection);tasks=TaskStore(connection);task=tasks.ingest(IngestedTicket("fake","42","Frozen repair",{"title":"Frozen repair"}),"demo","automatic");run_id=str(task["runs"][0]["id"]);tasks.claim_run(run_id)
        run_root=loaded.data_root/"tasks"/task["id"]/"runs"/run_id;freeze_root=run_root/"freeze-change";freeze_root.mkdir(parents=True);(freeze_root/"change.patch").write_bytes(patch_text.encode("utf-8"))
        manifest={"schema_version":1,"change_version":1,"modification_source":{"id":"source","base_revision":"abc123"},"diff":{"path":"change.patch","sha256":patch_sha},"files":[{"path":"app.txt","operation":"modify","content_sha256":"0"*64}],"source_commits":[],"verification_sha256":"1"*64,"review_sha256":"2"*64,"config_sha256":"3"*64};(freeze_root/"change-manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
        patch_filename="fix：【Python】【#B42】【v1】通用模块 - 问题修复  提交人：Tester.patch";delivery_metadata={"schema_version":1,"conventional_type":"fix","technology_tag":"Python","ticket_key":"B42","version_label":"v1","module_name":"通用模块","change_summary":"问题修复","submitter_name":"Tester","commit_subject":patch_filename[:-6],"patch_filename":patch_filename};(freeze_root/"delivery-metadata.json").write_text(json.dumps(delivery_metadata,ensure_ascii=False),encoding="utf-8")
        snapshot_root=run_root/"snapshot";snapshot_root.mkdir(parents=True);(snapshot_root/"config-snapshot.json").write_text(json.dumps({"schema_version":1,"project_sha256":"3"*64,"project":project}),encoding="utf-8")
        patch_output=loaded.data_root/"patches"/patch_filename;patch_output.parent.mkdir(parents=True);patch_output.write_bytes(patch_text.encode("utf-8"))
        recovered=RecoveryService(connection,loaded.data_root).recover_interrupted_runs();assert recovered=={"deliveryResume":1,"failedBeforeFreeze":0};assert tasks.get_run_summary(run_id)["status"]=="queued"
        result=RunExecutor(connection=connection,config_store=ConfigStore(loaded),contracts_root=contracts_root).execute(run_id);assert result.status=="completed" and result.result=="changed";assert len(result.deliveries)==1 and result.deliveries[0].detail["adoptedExisting"] is True;assert patch_output.read_text(encoding="utf-8")==patch_text
        detail=tasks.get_task(str(task["id"]));assert detail["status"]=="completed" and detail["result"]=="changed";action=detail["runs"][0]["delivery_actions"][0];assert action["status"]=="succeeded" and action["result"]["adoptedExisting"] is True
