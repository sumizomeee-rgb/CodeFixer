#!/usr/bin/env bash
set -euo pipefail
python -m pytest backend/tests/unit backend/tests/contract backend/tests/integration
if [[ -d frontend/node_modules ]]; then
  (cd frontend && npm run typecheck && npm run test:browser)
else
  echo "frontend/node_modules missing; run scripts/bootstrap.sh first" >&2
  exit 2
fi
