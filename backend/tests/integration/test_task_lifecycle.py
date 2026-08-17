import json
import hashlib
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


def test_completed_task_can_apply_frozen_files_to_localization(tmp_path: Path):
    loaded = _loaded(tmp_path)
    localization = tmp_path / "localization"
    localization.mkdir()
    (localization / "value.txt").write_text("old\n", encoding="utf-8")
    loaded.config.projects = [
        {
            "id": "project-a",
            "localizationSource": {
                "id": "localization-a",
                "path": str(localization),
            },
        }
    ]
    with TestClient(create_app(loaded)) as client:
        with connect_database(client.app.state.db_path) as db:
            store = TaskStore(db)
            task = store.ingest(
                IngestedTicket("tapd", "apply-1", "Bug", {"description": "wrong"}),
                "project-a",
                "automatic",
            )
            run_id = task["runs"][0]["id"]
            store.claim_run(run_id)
            store.complete_run(run_id, "changed")
        run_root = loaded.data_root / "tasks" / task["id"] / "runs" / run_id
        frozen = run_root / "freeze-change/files/value.txt"
        frozen.parent.mkdir(parents=True)
        content = b"new\n"
        frozen.write_bytes(content)
        (run_root / "freeze-change/change-manifest.json").write_text(
            json.dumps(
                {
                    "files": [
                        {
                            "path": "value.txt",
                            "operation": "modify",
                            "content_sha256": hashlib.sha256(content).hexdigest(),
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        (run_root / "snapshot").mkdir()
        (run_root / "snapshot/config-snapshot.json").write_text(
            json.dumps({"project": loaded.config.projects[0]}), encoding="utf-8"
        )

        response = client.post(f"/api/tasks/{task['id']}/apply-to-localization")

        assert response.status_code == 200
        assert response.json()["copied"] == 1
        assert (localization / "value.txt").read_text(encoding="utf-8") == "new\n"
