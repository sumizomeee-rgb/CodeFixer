from __future__ import annotations

import asyncio
import json
from pathlib import Path

from codefixer.config import AppConfig, LoadedConfig
from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.config_store import ConfigStore
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.task_store import TaskStore
from codefixer.orchestration.scheduler import Scheduler


def test_scheduler_uses_sqlite_queue_and_respects_capacity(tmp_path: Path):
    data=tmp_path/'data';data.mkdir();db=data/'codefixer.db';config=AppConfig.model_validate({'execution':{'mode':'automatic','maxConcurrentTasks':1,'maxRepairAttempts':3}});config_path=tmp_path/'config.json';config_path.write_text(json.dumps(config.model_dump(mode='json')),encoding='utf-8');loaded=LoadedConfig(config=config,base_config_path=config_path,data_root=data,frontend_dist=tmp_path/'frontend')
    with connect_database(db) as connection:
        apply_migrations(connection);store=TaskStore(connection);first=store.ingest(IngestedTicket('p','1','one',{}),'project','automatic');second=store.ingest(IngestedTicket('p','2','two',{}),'project','automatic');queued={first['runs'][0]['id'],second['runs'][0]['id']}
    called=[]
    def execute(run_id):
        called.append(run_id)
        with connect_database(db) as connection:
            store=TaskStore(connection);store.claim_run(run_id);store.complete_run(run_id,'changed')
    scheduler=Scheduler(db_path=db,config_store=ConfigStore(loaded),contracts_root=tmp_path,sleep_seconds=.01,execute_run=execute)
    async def once(): await scheduler.tick();await asyncio.sleep(.05);scheduler._reap()
    asyncio.run(once());assert len(called)==1 and called[0] in queued
    scheduler2=Scheduler(db_path=db,config_store=ConfigStore(loaded),contracts_root=tmp_path,sleep_seconds=.01,execute_run=execute);asyncio.run(scheduler2.tick());asyncio.run(asyncio.sleep(.05));scheduler2._reap();assert set(called)==queued
