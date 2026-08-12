#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:9522/api/readiness")
    args = parser.parse_args()
    with urllib.request.urlopen(args.url, timeout=5) as response:
        payload = json.load(response)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ready") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
