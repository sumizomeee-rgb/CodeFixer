import json
import subprocess
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from codefixer.config import load_config
from codefixer.infrastructure.database import connect_database
from codefixer.infrastructure.task_store import TaskStore
from codefixer.main import create_app


def _client(tmp_path: Path, monkeypatch):
    config_dir = tmp_path / "config"
    defaults = config_dir / "defaults" / "codefixer.json"
    defaults.parent.mkdir(parents=True)
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    remote = tmp_path / "remote.git"
    subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
    subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", str(remote)], check=True)
    (repo / "README.md").write_text("fixture\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@local", "commit", "-q", "-m", "fixture"], check=True)
    subprocess.run(["git", "-C", str(repo), "push", "-q", "-u", "origin", "HEAD"], check=True)
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
        project = {"id": "demo", "name": "Demo", "routingRules": [{"id": "primary", "providerRef": "tapd", "priority": 100, "catchAll": True, "versionFilter": {"mode": "selected", "versions": [{"id": "v47", "name": "4.7"}]}}], "localizationSource": {"type": "directory", "path": str(repository)}, "modificationWorkspace": {"locationType": "local", "localPath": str(repository), "allowedRoots": ["."], "deniedRoots": [], "allowedExtensions": []}, "deliveryLog": {"technologyTag": "Python", "submitterName": "Tester"}, "finalActions": [{"id": "patch", "type": "patch", "outputDirectory": str(tmp_path / "patches")}]}
        created = client.post("/api/projects", json=project, headers={"If-Match": etag})
        assert created.status_code == 201
        project_id = created.json()["project"]["id"]
        assert project_id.startswith("pipeline-")
        assert project_id != "demo"
        assert created.json()["project"]["intakeStartedAt"]
        assert created.json()["project"]["createdAt"] == created.json()["project"]["intakeStartedAt"]
        assert created.json()["project"]["pollIntervalSeconds"] == 1200
        assert created.json()["project"]["verification"] == {
            "timeoutSeconds": 1200,
            "steps": [],
            "allowNoAutomatedTests": True,
            "reason": "使用平台内置复核与交付前差异检查",
        }
        assert created.json()["project"]["routingRules"][0]["versionFilter"] == {"mode": "selected", "versions": [{"id": "v47", "name": "4.7"}]}
        assert created.json()["project"]["modificationWorkspace"]["vcsKind"] == "git"
        assert created.json()["project"]["modificationWorkspace"]["hostingKind"] == "other"
        assert created.json()["health"]["ready"] is True
        projects = client.get("/api/projects").json()
        assert projects["items"][0]["id"] == project_id
        assert projects["health"][project_id]["ready"] is True
        check_ids = {item["id"] for item in created.json()["health"]["checks"]}
        assert "agent.current" in check_ids
        assert not any(item.startswith("agent.scopeDiscovery") for item in check_ids)
        edited = client.put(
            f"/api/projects/{project_id}",
            json={**created.json()["project"], "pollIntervalSeconds": 1800},
            headers={"If-Match": created.json()["etag"]},
        )
        assert edited.status_code == 200
        assert edited.json()["project"]["pollIntervalSeconds"] == 1800
        secret = client.put("/api/secrets/company-gitlab", json={"value": "token-value"})
        assert secret.status_code == 200
        public = client.get("/api/settings").json()
        assert public["secrets"]["company-gitlab"] == {"configured": True}
        assert "token-value" not in json.dumps(public)

        incompatible = {**project, "finalActions": [{"id": "push", "type": "gitlabPush"}]}
        rejected = client.put(f"/api/projects/{project_id}", json=incompatible, headers={"If-Match": edited.json()["etag"]})
        assert rejected.status_code == 422
        assert "不支持 gitlabPush" in rejected.json()["error"]["message"]

        disabled = client.put(
            f"/api/projects/{project_id}/enabled",
            json={"enabled": False},
            headers={"If-Match": edited.json()["etag"]},
        )
        assert disabled.status_code == 200
        assert disabled.json()["project"]["enabled"] is False
        original_intake = disabled.json()["project"]["intakeStartedAt"]

        enabled = client.put(
            f"/api/projects/{project_id}/enabled",
            json={"enabled": True},
            headers={"If-Match": disabled.json()["etag"]},
        )
        assert enabled.status_code == 200
        assert enabled.json()["project"]["enabled"] is True
        assert enabled.json()["project"]["intakeStartedAt"] != original_intake
        cursor = client.app.state.db_path
        with connect_database(cursor) as connection:
            assert TaskStore(connection).get_cursor("tapd") == enabled.json()["project"]["intakeStartedAt"]

def test_provider_crud__generates_internal_id_and_keeps_name_editable(tmp_path: Path, monkeypatch):
    test_client, _ = _client(tmp_path, monkeypatch)
    with test_client as client:
        etag = client.get("/api/settings").json()["etag"]
        created = client.post(
            "/api/providers",
            headers={"If-Match": etag},
            json={
                "provider": {"name": "Haru", "type": "tapd", "workspaceId": "45286624", "auth": {"mode": "oauth"}, "pollIntervalSeconds": 60},
                "secrets": {"token": "token-value"},
            },
        )
        assert created.status_code == 201
        provider = created.json()["provider"]
        assert provider["id"].startswith("provider-")
        assert provider["id"] != provider["name"]
        assert provider["name"] == "Haru"
        assert "pollIntervalSeconds" not in provider

        renamed = client.put(
            f"/api/providers/{provider['id']}",
            headers={"If-Match": created.json()["etag"]},
            json={"provider": {**provider, "id": "user-cannot-change-this", "name": "Haru TAPD"}, "secrets": {}},
        )
        assert renamed.status_code == 200
        assert renamed.json()["provider"]["id"] == provider["id"]
        assert renamed.json()["provider"]["name"] == "Haru TAPD"


def test_provider_versions__explains_tapd_rate_limit(tmp_path: Path, monkeypatch):
    test_client, _ = _client(tmp_path, monkeypatch)
    with test_client as client:
        etag = client.get("/api/settings").json()["etag"]
        created = client.post(
            "/api/providers",
            headers={"If-Match": etag},
            json={
                "provider": {
                    "name": "Haru TAPD",
                    "type": "tapd",
                    "workspaceId": "45286624",
                    "auth": {"mode": "oauth"},
                },
                "secrets": {"token": "token"},
            },
        )
        provider_id = created.json()["provider"]["id"]

        def rate_limited(*args, **kwargs):
            del args, kwargs
            request = httpx.Request("GET", "https://api.tapd.cn/iterations")
            response = httpx.Response(429, request=request)
            raise httpx.HTTPStatusError("rate limited", request=request, response=response)

        monkeypatch.setattr(
            "codefixer.adapters.tickets.tapd.adapter.TapdTicketProvider.list_versions",
            rate_limited,
        )
        response = client.get(f"/api/providers/{provider_id}/versions")

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "provider_rate_limited"
    assert "全部版本" in response.json()["error"]["message"]
