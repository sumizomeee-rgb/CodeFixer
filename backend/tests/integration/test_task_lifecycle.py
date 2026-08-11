import json
from pathlib import Path

from fastapi.testclient import TestClient

from codefixer.config import AppConfig, LoadedConfig
from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.database import connect_database
from codefixer.infrastructure.task_store import TaskStore
from codefixer.main import create_app


def _loaded(tmp_path: Path, mode: str = 'awaitingStart') -> LoadedConfig:
    frontend = tmp_path / 'frontend'
    frontend.mkdir()
    (frontend / 'index.html').write_text('CodeFixer', encoding='utf-8')
    cfg = AppConfig.model_validate(
        {'execution': {'mode': mode, 'maxConcurrentTasks': 3, 'maxRepairAttempts': 3}}
    )
    config_path = tmp_path / 'codefixer.json'
    config_path.write_text(json.dumps(cfg.model_dump(mode='json')), encoding='utf-8')
    return LoadedConfig(
        config=cfg, base_config_path=config_path, data_root=tmp_path / 'data', frontend_dist=frontend
    )


def test_ingest_is_idempotent_and_manual_start_creates_single_run(tmp_path: Path):
    loaded = _loaded(tmp_path)
    with TestClient(create_app(loaded)) as client:
        with connect_database(client.app.state.db_path) as db:
            store = TaskStore(db)
            ticket = IngestedTicket(
                'tapd-main', '123', 'Bug A', {'title': 'Bug A', 'description': 'same'}, 'v1'
            )
            first = store.ingest(ticket, 'project-a', 'awaitingStart')
            second = store.ingest(ticket, 'project-a', 'awaitingStart')
            assert first['id'] == second['id']
            assert second['status'] == 'awaiting_start'
            assert db.execute('SELECT COUNT(*) FROM ticket_snapshots').fetchone()[0] == 1
        started = client.post(f"/api/tasks/{first['id']}/start")
        assert started.status_code == 200
        assert started.json()['status'] == 'queued'
        detail = client.get(f"/api/tasks/{first['id']}").json()
        assert len(detail['runs']) == 1
        assert client.post(f"/api/tasks/{first['id']}/start").status_code == 409
        assert client.post(f"/api/tasks/{first['id']}/cancel").json()['status'] == 'canceled'


def test_automatic_ingest_queues_one_active_run(tmp_path: Path):
    loaded = _loaded(tmp_path, 'automatic')
    with TestClient(create_app(loaded)) as client:
        with connect_database(client.app.state.db_path) as db:
            task = TaskStore(db).ingest(
                IngestedTicket('redmine', '9', 'Bug', {'x': 1}), 'project-r', 'automatic'
            )
            assert task['status'] == 'queued'
            assert len(task['runs']) == 1
            count = db.execute(
                "SELECT COUNT(*) FROM task_runs WHERE task_id=? AND status IN ('queued','running')",
                (task['id'],),
            ).fetchone()[0]
            assert count == 1
