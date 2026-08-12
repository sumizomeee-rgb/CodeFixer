from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


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
    @staticmethod
    def _native_cmd_proxy(shim: Path) -> Path | None:
        """Resolve simple npm-style CMD shims that forward directly to an exe."""
        try:
            content = shim.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        pattern = re.compile(r'^\s*"(?P<target>[^"]+\.exe)"\s+%\*\s*$', re.MULTILINE | re.IGNORECASE)
        match = pattern.search(content)
        if match is None:
            return None
        expanded = re.sub(
            r"%dp0%",
            lambda _: str(shim.parent),
            match.group("target"),
            flags=re.IGNORECASE,
        )
        target = Path(expanded)
        return target if target.is_file() else None

    @staticmethod
    def _prepare_command(command: list[str], process_env: Mapping[str, str]) -> list[str]:
        if not command:
            raise ValueError("process command is empty")
        resolved = shutil.which(command[0], path=process_env.get("PATH")) or command[0]
        if os.name == "nt" and Path(resolved).suffix.lower() in {".cmd", ".bat"}:
            native_proxy = SubprocessRunner._native_cmd_proxy(Path(resolved))
            if native_proxy is not None:
                resolved = str(native_proxy)
        # CreateProcess can launch a resolved .cmd/.bat shim directly. Agent CLIs
        # with a native proxy bypass the batch layer so JSON arguments stay exact.
        return [resolved, *command[1:]]

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
            self._prepare_command(command, process_env),
            cwd=cwd,
            stdin=subprocess.PIPE if stdin_text is not None else None,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=process_env,
            **kwargs,
        )
        deadline = started + timeout_seconds
        first_communicate = True
        while True:
            if cancel_check is not None and cancel_check():
                self._terminate_tree(process)
                stdout, stderr = process.communicate()
                return ProcessResult(
                    process.returncode,
                    stdout.decode("utf-8", errors="replace"),
                    stderr.decode("utf-8", errors="replace"),
                    False,
                    time.monotonic() - started,
                    True,
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._terminate_tree(process)
                stdout, stderr = process.communicate()
                return ProcessResult(
                    process.returncode,
                    stdout.decode("utf-8", errors="replace"),
                    stderr.decode("utf-8", errors="replace"),
                    True,
                    time.monotonic() - started,
                )
            try:
                stdout, stderr = process.communicate(
                    input=stdin_text.encode("utf-8") if first_communicate and stdin_text is not None else None,
                    timeout=min(0.25, remaining),
                )
                return ProcessResult(
                    process.returncode,
                    stdout.decode("utf-8", errors="replace"),
                    stderr.decode("utf-8", errors="replace"),
                    False,
                    time.monotonic() - started,
                )
            except subprocess.TimeoutExpired:
                first_communicate = False

    @staticmethod
    def _terminate_tree(process: subprocess.Popen[bytes]) -> None:
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
