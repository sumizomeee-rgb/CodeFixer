from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from codefixer.config import AppConfig, LoadedConfig
from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.config_store import ConfigStore
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.project_health_store import ProjectHealthStore
from codefixer.infrastructure.task_store import TaskStore
from codefixer.orchestration.scheduler import (
    Scheduler,
    _active_provider_intervals,
    _project_health_due,
)


def _loaded(tmp_path: Path, config: AppConfig) -> LoadedConfig:
    data = tmp_path / "data"
    data.mkdir()
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config.model_dump(mode="json")), encoding="utf-8")
    return LoadedConfig(
        config=config,
        base_config_path=config_path,
        data_root=data,
        frontend_dist=tmp_path / "frontend",
    )


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


def test_scheduler_does_not_poll_provider_without_enabled_pipeline(tmp_path: Path):
    config = AppConfig.model_validate(
        {
            "ticketProviders": [{"id": "provider-tapd", "name": "TAPD", "type": "tapd", "workspaceId": "101"}],
            "projects": [],
        }
    )
    loaded = _loaded(tmp_path, config)
    db = loaded.data_root / "codefixer.db"
    with connect_database(db) as connection:
        apply_migrations(connection)
    scheduler = Scheduler(db_path=db, config_store=ConfigStore(loaded), contracts_root=tmp_path)
    called: list[str] = []
    scheduler._poll_provider = lambda provider: called.append(str(provider["id"]))

    asyncio.run(scheduler.tick())

    assert called == []


def test_scheduler_only_polls_providers_referenced_by_enabled_pipelines(tmp_path: Path):
    config = AppConfig.model_validate(
        {
            "ticketProviders": [
                {"id": "provider-tapd", "name": "TAPD", "type": "tapd", "workspaceId": "101"},
                {"id": "provider-redmine", "name": "Redmine", "type": "redmine", "baseUrl": "https://redmine.test"},
            ],
            "projects": [
                {
                    "id": "active",
                    "name": "Active",
                    "enabled": True,
                    "routingRules": [{"id": "route", "providerRef": "provider-tapd"}],
                },
                {
                    "id": "disabled",
                    "name": "Disabled",
                    "enabled": False,
                    "routingRules": [{"id": "route", "providerRef": "provider-redmine"}],
                },
            ],
        }
    )
    loaded = _loaded(tmp_path, config)
    db = loaded.data_root / "codefixer.db"
    with connect_database(db) as connection:
        apply_migrations(connection)
        ProjectHealthStore(connection).put(
            {
                "projectId": "active",
                "ready": True,
                "status": "ready",
                "summary": "流水线已就绪",
                "checks": [],
            }
        )
    scheduler = Scheduler(db_path=db, config_store=ConfigStore(loaded), contracts_root=tmp_path)
    called: list[str] = []
    scheduler._poll_provider = lambda provider: called.append(str(provider["id"]))

    asyncio.run(scheduler.tick())

    assert called == ["provider-tapd"]


def test_project_health_schedule_is_anchored_to_creation_time():
    created = datetime(2026, 8, 17, 10, 20, tzinfo=UTC)

    assert _project_health_due(created.isoformat(), created.isoformat(), created + timedelta(hours=2, minutes=59)) is False
    assert _project_health_due(created.isoformat(), created.isoformat(), created + timedelta(hours=3)) is True
    assert _project_health_due(created.isoformat(), (created + timedelta(hours=3, minutes=1)).isoformat(), created + timedelta(hours=5)) is False
    assert _project_health_due(created.isoformat(), (created + timedelta(hours=3, minutes=1)).isoformat(), created + timedelta(hours=6)) is True


def test_active_provider_interval_defaults_to_twenty_minutes_and_uses_shortest_pipeline():
    projects = [
        {
            "id": "default",
            "routingRules": [{"providerRef": "provider-tapd"}],
        },
        {
            "id": "faster",
            "pollIntervalSeconds": 300,
            "routingRules": [{"providerRef": "provider-tapd"}],
        },
        {
            "id": "other",
            "pollIntervalSeconds": 1800,
            "routingRules": [{"providerRef": "provider-redmine"}],
        },
        {
            "id": "disabled",
            "enabled": False,
            "pollIntervalSeconds": 60,
            "routingRules": [{"providerRef": "provider-redmine"}],
        },
    ]

    assert _active_provider_intervals(projects) == {
        "provider-tapd": 300,
        "provider-redmine": 1800,
    }


def test_active_provider_interval_has_no_provider_type_branch():
    assert _active_provider_intervals(
        [
            {
                "id": "default",
                "routingRules": [
                    {"providerRef": "provider-tapd"},
                    {"providerRef": "provider-redmine"},
                ],
            }
        ]
    ) == {
        "provider-tapd": 1200,
        "provider-redmine": 1200,
    }


def test_scheduler_does_not_poll_provider_when_pipeline_health_is_red(tmp_path: Path):
    created = datetime.now(UTC).isoformat()
    config = AppConfig.model_validate(
        {
            "ticketProviders": [
                {"id": "provider-tapd", "name": "TAPD", "type": "tapd", "workspaceId": "101"}
            ],
            "projects": [
                {
                    "id": "broken",
                    "name": "Broken",
                    "enabled": True,
                    "createdAt": created,
                    "intakeStartedAt": created,
                    "routingRules": [{"id": "route", "providerRef": "provider-tapd"}],
                }
            ],
        }
    )
    loaded = _loaded(tmp_path, config)
    db = loaded.data_root / "codefixer.db"
    with connect_database(db) as connection:
        apply_migrations(connection)
        ProjectHealthStore(connection).put(
            {
                "projectId": "broken",
                "ready": False,
                "status": "not_ready",
                "summary": "仓库不可访问",
                "checks": [],
            }
        )
    scheduler = Scheduler(db_path=db, config_store=ConfigStore(loaded), contracts_root=tmp_path)
    called: list[str] = []
    scheduler._poll_provider = lambda provider: called.append(str(provider["id"]))

    asyncio.run(scheduler.tick())

    assert called == []
