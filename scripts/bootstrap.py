#!/usr/bin/env python3
"""Cross-platform CodeFixer bootstrap.

The only host prerequisites are a compatible Python plus Node.js/npm.
Project dependencies are installed into project-local directories:
- backend/.venv
- frontend/node_modules

Virtual environments and node_modules are intentionally disposable and should
be recreated after moving the repository to another machine.
"""

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
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def find_npm() -> str:
    npm = shutil.which("npm") or shutil.which("npm.cmd")
    if npm is None:
        raise SystemExit("npm not found. Install Node.js/npm first.")
    return npm


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap CodeFixer in-place")
    parser.add_argument(
        "--production",
        action="store_true",
        help="install backend runtime dependencies and build frontend/dist",
    )
    parser.add_argument(
        "--with-browser",
        action="store_true",
        help="also install Playwright Chromium hermetically under frontend/node_modules",
    )
    args = parser.parse_args()

    if sys.version_info < (3, 12):
        raise SystemExit("CodeFixer requires Python 3.12+")

    npm = find_npm()
    if not venv_python().exists():
        run([sys.executable, "-m", "venv", str(VENV)])

    py = str(venv_python())
    install_target = "-e ./backend" if args.production else "-e ./backend[dev]"
    run([py, "-m", "pip", "install", install_target], cwd=ROOT)

    # npm is local-by-default: dependencies land in frontend/node_modules.
    run([npm, "ci"], cwd=FRONTEND)

    if args.with_browser:
        browser_env = os.environ.copy()
        # Playwright's documented hermetic mode keeps Chromium inside node_modules.
        browser_env["PLAYWRIGHT_BROWSERS_PATH"] = "0"
        run([npm, "exec", "playwright", "install", "chromium"], cwd=FRONTEND, env=browser_env)

    if args.production:
        run([npm, "run", "build"], cwd=FRONTEND)

    print()
    print("CodeFixer bootstrap complete.")
    print(f"Python environment: {VENV}")
    print(f"Node dependencies:  {FRONTEND / 'node_modules'}")
    if args.production:
        print(f"Frontend build:      {FRONTEND / 'dist'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
