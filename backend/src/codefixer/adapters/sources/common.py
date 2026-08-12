from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Mapping

from codefixer.infrastructure.process_runner import ProcessResult, ProcessRunner, SubprocessRunner


class SourceCommandError(RuntimeError):
    pass


class CliSourceBase:
    def __init__(self, command_prefix: list[str], runner: ProcessRunner | None = None):
        if not command_prefix:
            raise ValueError("source command prefix cannot be empty")
        self.command_prefix = tuple(command_prefix)
        self.runner = runner or SubprocessRunner()

    def _run(
        self,
        args: list[str],
        *,
        cwd: Path,
        timeout: int = 120,
        env: Mapping[str, str] | None = None,
        allow_failure: bool = False,
    ) -> ProcessResult:
        result = self.runner.run(
            [*self.command_prefix, *args],
            cwd=cwd,
            stdin_text=None,
            env=env,
            timeout_seconds=timeout,
        )
        if result.timed_out:
            raise SourceCommandError(f"source command timed out: {' '.join(args)}")
        if not allow_failure and result.exit_code != 0:
            raise SourceCommandError(result.stderr.strip() or result.stdout.strip() or f"source command failed: {args}")
        return result


def patch_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
