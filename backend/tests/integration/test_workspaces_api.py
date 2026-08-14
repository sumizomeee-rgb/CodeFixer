from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi.testclient import TestClient

import codefixer.application.services.workspace_detection as workspace_detection
from codefixer.config import load_config
from codefixer.main import create_app


def _client(tmp_path: Path, monkeypatch) -> TestClient:
    defaults = tmp_path / "config" / "defaults" / "codefixer.json"
    defaults.parent.mkdir(parents=True)
    defaults.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "server": {"host": "127.0.0.1", "port": 9522},
                "storage": {"dataRoot": "../../data"},
                "execution": {"mode": "awaitingStart", "maxConcurrentTasks": 1, "maxRepairAttempts": 3},
            }
        ),
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    monkeypatch.setenv("CODEFIXER_LOCAL_CONFIG", str(tmp_path / "config" / "local.json"))
    monkeypatch.setenv("CODEFIXER_SECRET_CONFIG", str(tmp_path / "config" / "secrets.json"))
    monkeypatch.setenv("CODEFIXER_FRONTEND_DIST", str(frontend))
    return TestClient(create_app(load_config(defaults)))


def test_detect_and_browse_workspace(tmp_path: Path, monkeypatch):
    repository = tmp_path / "repository"
    child = repository / "src"
    child.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(repository)], check=True)
    subprocess.run(["git", "-C", str(repository), "remote", "add", "origin", "git@github.com:company/project.git"], check=True)
    original_run = workspace_detection._run

    def connected_remote(command: list[str], *, cwd: Path, timeout: int = 10):
        if command[:2] == ["git", "ls-remote"]:
            return subprocess.CompletedProcess(command, 0, "ref: refs/heads/main\tHEAD\nabc\tHEAD\n", "")
        return original_run(command, cwd=cwd, timeout=timeout)

    monkeypatch.setattr(workspace_detection, "_run", connected_remote)

    with _client(tmp_path, monkeypatch) as client:
        detected = client.post(
            "/api/workspaces/detect",
            json={"locationType": "local", "location": str(child)},
        )
        assert detected.status_code == 200
        assert detected.json() == {
            "locationType": "local",
            "location": str(child.resolve()),
            "ready": True,
            "vcsKind": "git",
            "hostingKind": "github",
            "repositoryRoot": str(repository.resolve()),
            "remoteUrl": "git@github.com:company/project.git",
            "summary": "已识别为 GitHub Git 工作区",
            "checks": detected.json()["checks"],
        }

        listing = client.post("/api/workspaces/browse", json={"path": str(repository)})
        assert listing.status_code == 200
        assert listing.json()["path"] == str(repository.resolve())
        assert {item["name"] for item in listing.json()["items"]} == {".git", "src"}


def test_browse_workspace__rejects_relative_path(tmp_path: Path, monkeypatch):
    with _client(tmp_path, monkeypatch) as client:
        response = client.post("/api/workspaces/browse", json={"path": "relative/path"})

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "absolute_path_required"


def test_detect_workspace__omits_unavailable_optional_metadata(tmp_path: Path, monkeypatch):
    plain_directory = tmp_path / "plain"
    plain_directory.mkdir()
    with _client(tmp_path, monkeypatch) as client:
        response = client.post(
            "/api/workspaces/detect",
            json={"locationType": "local", "location": str(plain_directory)},
        )

    assert response.status_code == 200
    assert response.json()["ready"] is False
    assert "repositoryRoot" not in response.json()
    assert "remoteUrl" not in response.json()
