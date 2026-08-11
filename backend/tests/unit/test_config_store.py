import json
from pathlib import Path

from codefixer.config import load_config
from codefixer.infrastructure.config_store import ConfigStore


def test_store__writes_minimal_local_override_and_never_secrets(tmp_path: Path, monkeypatch):
    base = tmp_path / "defaults" / "codefixer.json"
    base.parent.mkdir(parents=True)
    base.write_text(json.dumps({"schemaVersion": 1, "execution": {"mode": "awaitingStart", "maxConcurrentTasks": 3, "maxRepairAttempts": 3}}), encoding="utf-8")
    local = tmp_path / "local.json"
    secrets = tmp_path / "secrets.json"
    monkeypatch.setenv("CODEFIXER_LOCAL_CONFIG", str(local))
    monkeypatch.setenv("CODEFIXER_SECRET_CONFIG", str(secrets))
    store = ConfigStore(load_config(base))
    before = store.etag
    store.set_execution_mode("automatic")
    assert store.etag != before
    assert json.loads(local.read_text("utf-8")) == {"execution": {"mode": "automatic"}}
    store.set_secret("gitlab-token", "super-secret")
    assert "super-secret" not in local.read_text("utf-8")
    assert store.list_secrets() == {"gitlab-token": {"configured": True}}
