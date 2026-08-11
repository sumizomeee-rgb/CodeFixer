import json
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[3]


def test_default_config__matches_public_schema():
    schema = json.loads((ROOT / "contracts/config/server-config.schema.json").read_text("utf-8"))
    config = json.loads((ROOT / "config/defaults/codefixer.json").read_text("utf-8"))
    Draft202012Validator(schema).validate(config)
