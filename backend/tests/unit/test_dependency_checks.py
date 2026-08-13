from __future__ import annotations

import json
import sys
from pathlib import Path

from codefixer.config import load_config
from codefixer.infrastructure.dependency_checks import inspect_executable_dependencies


def test_current_global_model_is_required_and_available_without_version_policy(tmp_path: Path):
    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "execution": {"currentModelId": "current"},
                "agentProfiles": [
                    {"id": "current", "runtime": "codex", "executableRef": "current-cli"}
                ],
                "executableBindings": {
                    "current-cli": {"command": [sys.executable], "versionArgs": ["--version"]},
                    "unused-cli": {"command": ["definitely-not-installed-codefixer-cli"]},
                },
            }
        ),
        encoding="utf-8",
    )

    checks = {item["dependencyId"]: item for item in inspect_executable_dependencies(load_config(config))}

    assert checks["current-cli"]["required"] is True
    assert checks["current-cli"]["status"] == "ready"
    assert "可用" in checks["current-cli"]["summary"]
    assert checks["unused-cli"]["status"] == "inactive"
