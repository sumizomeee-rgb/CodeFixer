import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

from codefixer.config import load_config
from codefixer.main import create_app


def _client(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "config"
    defaults = config_dir / "defaults" / "codefixer.json"
    defaults.parent.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    defaults.write_text(json.dumps({"schemaVersion": 1, "server": {"host": "127.0.0.1", "port": 9522}, "storage": {"dataRoot": "../../data"}, "execution": {"mode": "awaitingStart", "maxConcurrentTasks": 3, "maxRepairAttempts": 3}, "agentProfiles": [{"id": "agent-default", "runtime": "codex", "executableRef": "git-cli"}], "executableBindings": {"git-cli": {"command": ["git"], "versionArgs": ["--version"], "versionConstraint": None}}, "pathBindings": {"repo": str(repo), "patches": "patches"}, "projects": []}), encoding="utf-8")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("CodeFixer", encoding="utf-8")
    monkeypatch.setenv("CODEFIXER_LOCAL_CONFIG", str(config_dir / "local.json"))
    monkeypatch.setenv("CODEFIXER_SECRET_CONFIG", str(config_dir / "secrets.json"))
    monkeypatch.setenv("CODEFIXER_FRONTEND_DIST", str(frontend))
    return TestClient(create_app(load_config(defaults)))


def test_project_crud_preflight_and_etag__is_persistent(tmp_path: Path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        etag = client.get("/api/settings").json()["etag"]
        conflict = client.put("/api/settings/execution-mode", json={"mode": "automatic"}, headers={"If-Match": "stale"})
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "config_version_conflict"
        changed = client.put("/api/settings/execution-mode", json={"mode": "automatic"}, headers={"If-Match": etag})
        assert changed.status_code == 200
        assert changed.json()["mode"] == "automatic"
        etag = changed.json()["etag"]
        project = {"id": "demo", "name": "Demo", "modificationSource": {"type": "git", "repositoryRef": "repo", "executableRef": "git-cli"}, "agents": {"discovery": "agent-default", "repair": "agent-default", "review": "agent-default"}, "verification": {"steps": [], "allowNoAutomatedTests": True, "reason": "fixture uses deterministic review"}, "finalActions": [{"id": "patch", "type": "patch", "outputDirectoryRef": "patches"}]}
        created = client.post("/api/projects", json=project, headers={"If-Match": etag})
        assert created.status_code == 201
        assert client.get("/api/projects").json()["items"][0]["id"] == "demo"
        preflight = client.post("/api/projects/demo/preflight")
        assert preflight.status_code == 200
        assert preflight.json()["ready"] is True
        secret = client.put("/api/secrets/company-gitlab", json={"value": "token-value"})
        assert secret.status_code == 200
        public = client.get("/api/settings").json()
        assert public["secrets"]["company-gitlab"] == {"configured": True}
        assert "token-value" not in json.dumps(public)
