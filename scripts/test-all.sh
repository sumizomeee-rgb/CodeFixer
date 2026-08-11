#!/usr/bin/env bash
set -euo pipefail
./scripts/test-fast.sh
(cd frontend && npm run build && npm run test:e2e)
