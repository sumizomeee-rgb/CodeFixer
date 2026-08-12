#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
test -x backend/.venv/bin/python || { echo "Project venv missing; run scripts/bootstrap.sh" >&2; exit 1; }
exec backend/.venv/bin/python scripts/test.py --all
