from __future__ import annotations

from pathlib import Path

from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.task_store import TaskStore
from codefixer.orchestration.recovery import RecoveryService


def _running(store: TaskStore, ticket_id: str):
    task=store.ingest(IngestedTicket('p',ticket_id,'t',{}),'project','automatic');run=task['runs'][0]['id'];store.claim_run(run);return task['id'],run


def test_recovery_fails_pre_freeze_but_requeues_frozen_delivery(tmp_path: Path):
    data=tmp_path/'data';data.mkdir()
    with connect_database(data/'db.sqlite') as connection:
        apply_migrations(connection);store=TaskStore(connection);task_a,run_a=_running(store,'1');task_b,run_b=_running(store,'2');freeze=data/'tasks'/task_b/'runs'/run_b/'freeze-change';freeze.mkdir(parents=True);(freeze/'change-manifest.json').write_text('{}',encoding='utf-8')
        result=RecoveryService(connection,data).recover_interrupted_runs();assert result=={'deliveryResume':1,'failedBeforeFreeze':1};assert store.get_run_summary(run_a)['status']=='failed';assert store.get_run_summary(run_b)['status']=='queued';assert store.get_task(task_a)['failure']['code']=='service_interrupted_before_freeze'
