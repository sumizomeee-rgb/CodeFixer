from pathlib import Path

from fastapi.testclient import TestClient

from codefixer.config import AppConfig, LoadedConfig
from codefixer.main import create_app


def _loaded(tmp_path: Path) -> LoadedConfig:
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("<h1>CodeFixer</h1>", encoding="utf-8")
    config_path = tmp_path / "codefixer.json"
    config_path.write_text("{}", encoding="utf-8")
    return LoadedConfig(
        config=AppConfig(),
        base_config_path=config_path,
        data_root=tmp_path / "data",
        frontend_dist=frontend,
    )


def test_health_and_readiness__when_phase0_runtime_is_valid(tmp_path: Path):
    with TestClient(create_app(_loaded(tmp_path))) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        readiness = client.get("/api/readiness")
        assert readiness.status_code == 200
        assert readiness.json()["ready"] is True
        assert {x["id"] for x in readiness.json()["checks"]} == {
            "config.loaded",
            "storage.data_root",
            "sqlite.wal",
            "frontend.dist",
        }

        page = client.get("/")
        assert page.status_code == 200
        assert "CodeFixer" in page.text
