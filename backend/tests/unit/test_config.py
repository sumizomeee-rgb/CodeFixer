import json
from pathlib import Path

from codefixer.config import load_config


def test_data_root__resolves_relative_to_base_config(tmp_path: Path):
    config_path = tmp_path / "config" / "codefixer.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        '{"schemaVersion":1,"storage":{"dataRoot":"../runtime"}}', encoding="utf-8"
    )
    loaded = load_config(config_path)
    assert loaded.data_root == (tmp_path / "runtime").resolve()


def test_default_machine_files_live_under_single_local_directory(tmp_path: Path):
    config_path = tmp_path / "config" / "defaults" / "codefixer.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"schemaVersion":1}', encoding="utf-8")

    loaded = load_config(config_path)

    assert loaded.local_config_path == (tmp_path / ".local" / "config.json").resolve()
    assert loaded.secrets_config_path == (tmp_path / ".local" / "secrets.json").resolve()


def test_legacy_agent_profile_id__migrates_to_current_model(tmp_path: Path, monkeypatch):
    config_path = tmp_path / "config" / "defaults" / "codefixer.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(
        json.dumps({
            "schemaVersion": 1,
            "execution": {"currentModelId": "claude-sonnet"},
        }),
        encoding="utf-8",
    )
    local_path = tmp_path / "config" / "local.json"
    local_path.write_text(json.dumps({"execution": {"agentProfileId": "gpt-5.6-sol"}}), encoding="utf-8")
    monkeypatch.setenv("CODEFIXER_LOCAL_CONFIG", str(local_path))

    loaded = load_config(config_path)

    assert loaded.config.execution.currentModelId == "gpt-5.6-sol"
