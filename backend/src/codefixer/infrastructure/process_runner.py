from __future__ import annotations

import os
import signal
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Protocol


@dataclass(frozen=True)
class ProcessResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration_seconds: float
    canceled: bool = False


class ProcessRunner(Protocol):
    def run(
        self,
        command: list[str],
        *,
        cwd: Path,
        stdin_text: str | None,
        env: Mapping[str, str] | None,
        timeout_seconds: int,
    ) -> ProcessResult: ...


class SubprocessRunner:
    def run(
        self,
        command: list[str],
        *,
        cwd: Path,
        stdin_text: str | None,
        env: Mapping[str, str] | None,
        timeout_seconds: int,
    ) -> ProcessResult:
        return self.run_cancelable(
            command,
            cwd=cwd,
            stdin_text=stdin_text,
            env=env,
            timeout_seconds=timeout_seconds,
            cancel_check=None,
        )

    def run_cancelable(
        self,
        command: list[str],
        *,
        cwd: Path,
        stdin_text: str | None,
        env: Mapping[str, str] | None,
        timeout_seconds: int,
        cancel_check: Callable[[], bool] | None,
    ) -> ProcessResult:
        started = time.monotonic()
        process_env = os.environ.copy()
        if env:
            process_env.update(env)
        kwargs: dict[str, object] = {}
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=process_env,
            **kwargs,
        )
        deadline = started + timeout_seconds
        first_communicate = True
        while True:
            if cancel_check is not None and cancel_check():
                self._terminate_tree(process)
                stdout, stderr = process.communicate()
                return ProcessResult(process.returncode, stdout, stderr, False, time.monotonic() - started, True)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._terminate_tree(process)
                stdout, stderr = process.communicate()
                return ProcessResult(process.returncode, stdout, stderr, True, time.monotonic() - started)
            try:
                stdout, stderr = process.communicate(
                    input=stdin_text if first_communicate else None,
                    timeout=min(0.25, remaining),
                )
                return ProcessResult(process.returncode, stdout, stderr, False, time.monotonic() - started)
            except subprocess.TimeoutExpired:
                first_communicate = False

    @staticmethod
    def _terminate_tree(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
            process.wait(timeout=2)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
