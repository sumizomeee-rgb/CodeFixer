#!/usr/bin/env bash
set -euo pipefail
python -m venv backend/.venv
backend/.venv/bin/python -m pip install -U pip
backend/.venv/bin/python -m pip install -e './backend[dev]'
(cd frontend && npm ci && npx playwright install chromium)
