import json
from pathlib import Path

from codefixer.config import AppConfig, LoadedConfig
from codefixer.main import create_app
from fastapi.testclient import TestClient


def test_scn_000_phase0_foundation_ready(tmp_path: Path):
    root = Path(__file__).resolve().parent
    scenario = json.loads((root / "SCN-000-phase0-ready/scenario.json").read_text("utf-8"))
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("维修控制台", encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    loaded = LoadedConfig(
        config=AppConfig(), base_config_path=config_path, data_root=tmp_path / "data", frontend_dist=frontend
    )
    with TestClient(create_app(loaded)) as client:
        assert client.get('/api/health').json()['status'] == scenario['expected']['health']
        assert client.get('/api/readiness').json()['ready'] is scenario['expected']['readiness']
        assert scenario['expected']['frontendMarker'] in client.get('/').text
