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
    defaults.write_text(json.dumps({"schemaVersion": 1, "server": {"host": "127.0.0.1", "port": 9522}, "storage": {"dataRoot": "../../data"}, "execution": {"mode": "awaitingStart", "currentModelId": "agent-default", "maxConcurrentTasks": 3, "maxRepairAttempts": 3}, "agentProfiles": [{"id": "agent-default", "runtime": "codex", "executableRef": "git-cli"}], "executableBindings": {"git-cli": {"command": ["git"], "versionArgs": ["--version"], "versionConstraint": None}}, "projects": []}), encoding="utf-8")
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    (frontend / "index.html").write_text("CodeFixer", encoding="utf-8")
    monkeypatch.setenv("CODEFIXER_LOCAL_CONFIG", str(config_dir / "local.json"))
    monkeypatch.setenv("CODEFIXER_SECRET_CONFIG", str(config_dir / "secrets.json"))
    monkeypatch.setenv("CODEFIXER_FRONTEND_DIST", str(frontend))
    return TestClient(create_app(load_config(defaults))), repo


def test_project_crud_preflight_and_etag__is_persistent(tmp_path: Path, monkeypatch):
    test_client, repo = _client(tmp_path, monkeypatch)
    with test_client as client:
        etag = client.get("/api/settings").json()["etag"]
        conflict = client.put("/api/settings/execution-mode", json={"mode": "automatic"}, headers={"If-Match": "stale"})
        assert conflict.status_code == 409
        assert conflict.json()["error"]["code"] == "config_version_conflict"
        changed = client.put("/api/settings/execution-mode", json={"mode": "automatic"}, headers={"If-Match": etag})
        assert changed.status_code == 200
        assert changed.json()["mode"] == "automatic"
        etag = changed.json()["etag"]
        repository = repo
        project = {"id": "demo", "name": "Demo", "localizationSource": {"type": "directory", "path": str(repository)}, "modificationWorkspace": {"path": str(repository), "allowedRoots": ["."], "deniedRoots": [], "allowedExtensions": []}, "verification": {"steps": [], "allowNoAutomatedTests": True, "reason": "fixture uses deterministic review"}, "finalActions": [{"id": "patch", "type": "patch", "outputDirectory": str(tmp_path / "patches")}]}
        created = client.post("/api/projects", json=project, headers={"If-Match": etag})
        assert created.status_code == 201
        assert created.json()["project"]["modificationWorkspace"]["vcsKind"] == "git"
        assert created.json()["project"]["modificationWorkspace"]["hostingKind"] == "other"
        assert client.get("/api/projects").json()["items"][0]["id"] == "demo"
        preflight = client.post("/api/projects/demo/preflight")
        assert preflight.status_code == 200
        assert preflight.json()["ready"] is True
        check_ids = {item["id"] for item in preflight.json()["checks"]}
        assert "agent.current" in check_ids
        assert not any(item.startswith("agent.scopeDiscovery") for item in check_ids)
        secret = client.put("/api/secrets/company-gitlab", json={"value": "token-value"})
        assert secret.status_code == 200
        public = client.get("/api/settings").json()
        assert public["secrets"]["company-gitlab"] == {"configured": True}
        assert "token-value" not in json.dumps(public)

        incompatible = {**project, "finalActions": [{"id": "mr", "type": "gitlabMr", "targetBranches": ["main"]}]}
        rejected = client.put("/api/projects/demo", json=incompatible, headers={"If-Match": created.json()["etag"]})
        assert rejected.status_code == 422
        assert "不支持 gitlabMr" in rejected.json()["error"]["message"]
