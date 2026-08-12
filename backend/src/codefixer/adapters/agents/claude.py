from __future__ import annotations

import json
from collections.abc import Mapping

from codefixer.adapters.agents.base import BaseCliAgentRuntime, first_string, load_schema, numeric, stage_prompt
from codefixer.application.ports.agents import AgentRequest, AgentRunResult
from codefixer.infrastructure.process_runner import ProcessResult

_READ_ONLY_TOOLS = "Read,Glob,Grep,Bash"
_WRITE_TOOLS = "Read,Glob,Grep,Bash,Edit,Write"
_READ_ONLY_ALLOWED = ("Read", "Glob", "Grep")
_WRITE_ALLOWED = ("Read", "Glob", "Grep", "Edit", "Write")


def _claude_compatible_schema(value: object) -> object:
    """Translate repository Draft 2020-12 metadata to Claude CLI's validator subset."""
    if isinstance(value, list):
        return [_claude_compatible_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, object] = {}
    for key, child in value.items():
        if key == "$schema":
            continue
        normalized_key = "definitions" if key == "$defs" else key
        normalized_child = _claude_compatible_schema(child)
        if normalized_key == "$ref" and isinstance(normalized_child, str):
            normalized_child = normalized_child.replace("#/$defs/", "#/definitions/")
        result[normalized_key] = normalized_child
    return result


class ClaudeCodeRuntime(BaseCliAgentRuntime):
    runtime_name = "claudeCode"

    def build_invocation(
        self, request: AgentRequest
    ) -> tuple[list[str], str | None, Mapping[str, str] | None]:
        writable = request.access == "workspace_write"
        command = [
            *self.command_prefix,
            "--bare",
            "-p",
            stage_prompt(request.entry_file),
            "--output-format",
            "json",
            "--no-session-persistence",
            "--permission-mode",
            "dontAsk",
            "--tools",
            _WRITE_TOOLS if writable else _READ_ONLY_TOOLS,
            "--allowedTools",
            *(_WRITE_ALLOWED if writable else _READ_ONLY_ALLOWED),
        ]
        if self.profile.model:
            command.extend(["--model", self.profile.model])
        if self.profile.effort:
            command.extend(["--effort", self.profile.effort])
        if self.profile.max_budget_usd is not None:
            command.extend(["--max-budget-usd", str(self.profile.max_budget_usd)])
        schema = load_schema(request.output_schema)
        if schema is not None:
            compatible_schema = _claude_compatible_schema(schema)
            command.extend(["--json-schema", json.dumps(compatible_schema, separators=(",", ":"))])
        command.extend(self.profile.extra_args)
        return command, None, None

    def parse_result(
        self, request: AgentRequest, command: list[str], process: ProcessResult
    ) -> AgentRunResult:
        payload: dict[str, object] = {}
        try:
            value = json.loads(process.stdout) if process.stdout.strip() else {}
            if isinstance(value, dict):
                payload = value
        except json.JSONDecodeError:
            pass
        structured = payload.get("structured_output")
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        return AgentRunResult(
            status=self.status(process),
            exit_code=process.exit_code,
            session_id=first_string((payload.get("session_id"), payload.get("sessionId"))),
            structured_output=structured,
            final_text=first_string((payload.get("result"), payload.get("text"))),
            usage=dict(usage),
            cost_usd=numeric(payload.get("total_cost_usd")) or numeric(payload.get("cost_usd")),
            events=(payload,) if payload else (),
            stderr=process.stderr,
            duration_seconds=process.duration_seconds,
            command=tuple(command),
        )
