from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Mapping

from codefixer.application.ports.agents import AgentProfile, AgentRequest, AgentRunResult, AgentRunStatus
from codefixer.infrastructure.process_runner import ProcessResult, ProcessRunner, SubprocessRunner


class AgentRuntimeError(ValueError):
    pass


def stage_prompt(entry_file: Path) -> str:
    path = entry_file.resolve()
    return (
        "Read and follow the CodeFixer stage entry document at this absolute path:\n"
        f"{path}\n\n"
        "Do not ask the user for clarification. Complete the stage autonomously within the granted "
        "workspace permissions and return the requested structured result."
    )


def load_schema(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AgentRuntimeError(f"output schema root must be object: {path}")
    return value


def parse_json_lines(text: str) -> tuple[dict[str, object], ...]:
    events: list[dict[str, object]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            events.append(value)
    return tuple(events)


def nested_get(value: object, *keys: str) -> object | None:
    current = value
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def first_string(values: Iterable[object | None]) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value
    return None


def numeric(value: object | None) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


class BaseCliAgentRuntime(ABC):
    runtime_name = "base"

    def __init__(
        self,
        profile: AgentProfile,
        command_prefix: list[str],
        runner: ProcessRunner | None = None,
    ) -> None:
        if not command_prefix:
            raise AgentRuntimeError("agent executable command is empty")
        self.profile = profile
        self.command_prefix = tuple(command_prefix)
        self.runner = runner or SubprocessRunner()

    def run(self, request: AgentRequest) -> AgentRunResult:
        self._validate_request(request)
        command, stdin_text, env = self.build_invocation(request)
        timeout = request.timeout_seconds or self.profile.timeout_seconds
        if isinstance(self.runner, SubprocessRunner):
            process = self.runner.run_cancelable(
                command,
                cwd=request.cwd.resolve(),
                stdin_text=stdin_text,
                env=env,
                timeout_seconds=timeout,
                cancel_check=request.cancel_check,
            )
        else:
            process = self.runner.run(
                command,
                cwd=request.cwd.resolve(),
                stdin_text=stdin_text,
                env=env,
                timeout_seconds=timeout,
            )
        return self.parse_result(request, command, process)

    @staticmethod
    def _validate_request(request: AgentRequest) -> None:
        if not request.entry_file.is_file():
            raise AgentRuntimeError(f"stage entry file does not exist: {request.entry_file}")
        if not request.cwd.is_dir():
            raise AgentRuntimeError(f"agent cwd does not exist: {request.cwd}")
        if request.output_schema is not None and not request.output_schema.is_file():
            raise AgentRuntimeError(f"output schema does not exist: {request.output_schema}")

    @abstractmethod
    def build_invocation(
        self, request: AgentRequest
    ) -> tuple[list[str], str | None, Mapping[str, str] | None]: ...

    @abstractmethod
    def parse_result(
        self, request: AgentRequest, command: list[str], process: ProcessResult
    ) -> AgentRunResult: ...

    @staticmethod
    def status(process: ProcessResult) -> AgentRunStatus:
        if process.canceled:
            return "canceled"
        if process.timed_out:
            return "timed_out"
        return "succeeded" if process.exit_code == 0 else "failed"
