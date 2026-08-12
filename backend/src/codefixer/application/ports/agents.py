from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

AgentStage = Literal["discovery", "no_change_verify", "repair", "review"]
AgentAccess = Literal["read_only", "workspace_write"]
AgentRunStatus = Literal["succeeded", "failed", "timed_out", "canceled"]
AgentRuntimeName = Literal["claudeCode", "codex", "opencode"]


@dataclass(frozen=True)
class AgentProfile:
    id: str
    runtime: AgentRuntimeName
    executable_ref: str
    model: str | None = None
    effort: str | None = None
    timeout_seconds: int = 1800
    max_budget_usd: float | None = None
    extra_args: tuple[str, ...] = ()


@dataclass(frozen=True)
class AgentRequest:
    stage: AgentStage
    entry_file: Path
    cwd: Path
    access: AgentAccess
    timeout_seconds: int | None = None
    output_schema: Path | None = None
    cancel_check: Callable[[], bool] | None = None


@dataclass(frozen=True)
class AgentRunResult:
    status: AgentRunStatus
    exit_code: int | None
    session_id: str | None
    structured_output: object | None
    final_text: str | None = None
    usage: dict[str, object] = field(default_factory=dict)
    cost_usd: float | None = None
    events: tuple[dict[str, object], ...] = ()
    stderr: str = ""
    duration_seconds: float = 0.0
    command: tuple[str, ...] = ()


class AgentRuntime(Protocol):
    runtime_name: str

    def run(self, request: AgentRequest) -> AgentRunResult: ...
