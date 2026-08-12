#!/usr/bin/env python3
"""Cross-platform deterministic CodeFixer test entrypoint."""
from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
VENV_PY = ROOT / "backend" / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, env=env, check=True)


def npm_command() -> str:
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm") or shutil.which("npm")
    if npm is None:
        raise SystemExit("npm not found")
    return npm


def wait_ready(url: str, timeout: float = 30) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if b'"ready":true' in response.read().replace(b" ", b""):
                    return
        except Exception:
            pass
        time.sleep(.25)
    raise RuntimeError("CodeFixer test server did not become ready")


def stop_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=5)
        except Exception:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true", help="include browser component + same-origin E2E/visual tests")
    args = parser.parse_args()
    if not VENV_PY.exists() or not (FRONTEND / "node_modules").is_dir():
        raise SystemExit("Project dependencies missing. Run scripts/bootstrap.ps1 or scripts/bootstrap.sh")
    probe = subprocess.run(
        [str(VENV_PY), "-c", "import sys; assert sys.version_info >= (3,12) and sys.maxsize > 2**32"],
        check=False,
    )
    if probe.returncode != 0:
        raise SystemExit("backend/.venv must use 64-bit CPython 3.12+. Remove it and rerun bootstrap.")
    npm = npm_command()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "backend" / "src")
    run([str(VENV_PY), "-m", "pytest", "backend/tests", "tests/scenarios", "-q"], env=env)
    run([npm, "run", "typecheck"], cwd=FRONTEND)
    run([npm, "run", "build"], cwd=FRONTEND)
    if not args.all:
        return 0
    browser_env = os.environ.copy()
    browser_env["PLAYWRIGHT_BROWSERS_PATH"] = "0"
    run([npm, "run", "test:browser"], cwd=FRONTEND, env=browser_env)
    with tempfile.TemporaryDirectory(prefix="codefixer-e2e-") as temp:
        server_env = os.environ.copy()
        server_env.update({
            "CODEFIXER_DATA_ROOT": str(Path(temp) / "data"),
            "CODEFIXER_DISABLE_BACKGROUND": "1",
            "CODEFIXER_FRONTEND_DIST": str(FRONTEND / "dist"),
        })
        run([str(VENV_PY), "scripts/seed_demo.py", "--reset"], env=server_env)
        kwargs: dict[str, object] = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(
            [str(VENV_PY), "-m", "uvicorn", "codefixer.main:app", "--host", "127.0.0.1", "--port", "9522"],
            cwd=ROOT,
            env=server_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            **kwargs,
        )
        try:
            wait_ready("http://127.0.0.1:9522/api/readiness")
            run([npm, "run", "test:e2e"], cwd=FRONTEND, env=browser_env)
        finally:
            stop_process(process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
