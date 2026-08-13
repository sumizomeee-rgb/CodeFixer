#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = ROOT / "backend" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CodeFixer from project-local dependencies")
    parser.add_argument("--build", action="store_true", help="build frontend before starting")
    parser.add_argument("--build-only", action="store_true", help="build frontend and exit without starting the server")
    args = parser.parse_args()
    if not VENV_PY.exists():
        raise SystemExit("backend/.venv is missing. Run scripts/bootstrap.ps1 or scripts/bootstrap.sh")
    probe = subprocess.run(
        [str(VENV_PY), "-c", "import sys; assert sys.version_info >= (3,12) and sys.maxsize > 2**32"],
        check=False,
    )
    if probe.returncode != 0:
        raise SystemExit("backend/.venv must use 64-bit CPython 3.12+. Remove it and rerun bootstrap.")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if args.build or args.build_only:
        if npm is None:
            raise SystemExit("npm not found")
        subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
    if args.build_only:
        return 0
    if not (ROOT / "frontend" / "dist" / "index.html").is_file():
        raise SystemExit("frontend/dist is missing. Run with --build or: cd frontend && npm run build")
    env = os.environ.copy()
    env["CODEFIXER_FRONTEND_DIST"] = str(ROOT / "frontend" / "dist")
    return subprocess.call([str(VENV_PY), "-m", "codefixer"], cwd=ROOT, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
