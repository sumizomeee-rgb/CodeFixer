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
