#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for candidate in python3.12 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; assert sys.version_info >= (3,12) and sys.maxsize > 2**32' >/dev/null 2>&1; then
    exec "$candidate" scripts/bootstrap.py "$@"
  fi
done
echo "CodeFixer requires 64-bit CPython 3.12+. Install it and rerun bootstrap.sh." >&2
exit 1
