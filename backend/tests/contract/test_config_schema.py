import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]


def test_default_config__matches_public_schema():
    schema = json.loads((ROOT / "contracts/config/server-config.schema.json").read_text("utf-8"))
    config = json.loads((ROOT / "config/defaults/codefixer.json").read_text("utf-8"))
    Draft202012Validator(schema).validate(config)


def test_workspace_detection_contract__accepts_public_response_shape():
    schema = json.loads((ROOT / "contracts/config/workspace-detection.schema.json").read_text("utf-8"))
    response = {
        "path": "D:/repo",
        "ready": True,
        "vcsKind": "git",
        "hostingKind": "github",
        "repositoryRoot": "D:/repo",
        "remoteUrl": "git@github.com:company/repo.git",
        "summary": "已识别为 GitHub Git 工作区",
        "checks": [{"id": "workspace.vcs", "status": "ready", "summary": "Git 工作区可识别"}],
    }

    Draft202012Validator(schema).validate(response)


def test_server_config_contract__accepts_new_project_sources_and_actions():
    schema = json.loads((ROOT / "contracts/config/server-config.schema.json").read_text("utf-8"))
    config = json.loads((ROOT / "config/defaults/codefixer.json").read_text("utf-8"))
    config["projects"] = [
        {
            "id": "demo",
            "name": "Demo",
            "localizationSource": {"id": "knowledge", "type": "directory", "path": "D:/knowledge"},
            "modificationWorkspace": {
                "id": "workspace",
                "path": "D:/repo",
                "vcsKind": "git",
                "hostingKind": "github",
                "repositoryRoot": "D:/repo",
                "remoteUrl": "git@github.com:company/repo.git",
                "allowedRoots": ["."],
                "deniedRoots": ["generated"],
                "allowedExtensions": [".py"],
            },
            "deliveryLog": {
                "technologyTag": "Python",
                "submitterName": "Tester",
            },
            "finalActions": [
                {"id": "patch", "type": "patch", "outputDirectory": "D:/patches"},
                {"id": "pr", "type": "githubPr", "targetBranches": ["main"]},
            ],
        }
    ]

    Draft202012Validator(schema).validate(config)
