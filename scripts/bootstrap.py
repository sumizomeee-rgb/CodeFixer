#!/usr/bin/env python3
"""Create CodeFixer's disposable project-local dependency environments."""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".venv"


def run(command: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, env=env, check=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def find_npm() -> str:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if npm is None:
        raise SystemExit("npm not found. Install Node.js 22+ first.")
    return npm


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap CodeFixer in-place")
    parser.add_argument("--production", action="store_true", help="runtime Python deps + frontend production build")
    parser.add_argument("--with-browser", action="store_true", help="also install Playwright Chromium inside frontend/node_modules")
    args = parser.parse_args()
    if sys.version_info < (3, 12):
        raise SystemExit("CodeFixer requires Python 3.12+")
    npm = find_npm()
    if not venv_python().exists():
        run([sys.executable, "-m", "venv", str(VENV)])
    py = str(venv_python())
    run([py, "-m", "pip", "install", "--upgrade", "pip"])
    target = "./backend" if args.production else "./backend[dev]"
    run([py, "-m", "pip", "install", "-e", target], cwd=ROOT)
    run([npm, "ci"], cwd=FRONTEND)
    if args.with_browser:
        browser_env = os.environ.copy()
        browser_env["PLAYWRIGHT_BROWSERS_PATH"] = "0"
        run([npm, "exec", "--", "playwright", "install", "chromium"], cwd=FRONTEND, env=browser_env)
    if args.production:
        run([npm, "run", "build"], cwd=FRONTEND)
    print("\nCodeFixer bootstrap complete")
    print(f"  Python: {VENV}")
    print(f"  Node:   {FRONTEND / 'node_modules'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
