from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from codefixer.infrastructure.process_runner import ProcessRunner, SubprocessRunner


@dataclass(frozen=True)
class VerificationStep:
    id: str
    command: tuple[str, ...]
    cwd: Path | None = None
    timeout_seconds: int = 300
    required: bool = True
    env: Mapping[str, str] | None = None
    working_directory: str = "."


class VerificationRunner:
    def __init__(self, runner: ProcessRunner | None = None):
        self.runner = runner or SubprocessRunner()

    def run(
        self,
        candidate_sha256: str,
        steps: tuple[VerificationStep, ...],
        *,
        default_cwd: Path | None = None,
        cancel_check: Callable[[], bool] | None = None,
    ) -> dict[str, object]:
        results: list[dict[str, object]] = []
        passed = True
        for step in steps:
            if step.cwd is not None:
                cwd = step.cwd.resolve()
            elif default_cwd is not None:
                cwd = (default_cwd / step.working_directory).resolve()
                try:
                    cwd.relative_to(default_cwd.resolve())
                except ValueError as exc:
                    raise ValueError(f"verification step {step.id} escapes workspace") from exc
            else:
                raise ValueError(f"verification step {step.id} has no working directory")
            if not cwd.is_dir():
                raise ValueError(f"verification step {step.id} working directory does not exist: {cwd}")
            if isinstance(self.runner, SubprocessRunner):
                result = self.runner.run_cancelable(
                    list(step.command),
                    cwd=cwd,
                    stdin_text=None,
                    env=step.env,
                    timeout_seconds=step.timeout_seconds,
                    cancel_check=cancel_check,
                )
            else:
                result = self.runner.run(
                    list(step.command),
                    cwd=cwd,
                    stdin_text=None,
                    env=step.env,
                    timeout_seconds=step.timeout_seconds,
                )
            step_passed = not result.timed_out and not result.canceled and result.exit_code == 0
            if step.required and not step_passed:
                passed = False
            results.append(
                {
                    "id": step.id,
                    "required": step.required,
                    "passed": step_passed,
                    "exit_code": result.exit_code,
                    "timed_out": result.timed_out,
                    "canceled": result.canceled,
                    "duration_seconds": result.duration_seconds,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                }
            )
        return {
            "schema_version": 1,
            "candidate_sha256": candidate_sha256,
            "passed": passed,
            "steps": results,
        }
