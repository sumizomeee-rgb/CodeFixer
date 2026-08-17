from __future__ import annotations

import json
import os
from collections.abc import Mapping

from codefixer.adapters.agents.base import BaseCliAgentRuntime, first_string, nested_get, parse_json_lines, stage_prompt
from codefixer.application.ports.agents import AgentRequest, AgentRunResult
from codefixer.infrastructure.process_runner import ProcessResult

_READ_ONLY_PERMISSION = {
    "*": "deny",
    "read": "allow",
    "glob": "allow",
    "grep": "allow",
    "lsp": "allow",
    "external_directory": "deny",
    "edit": "deny",
    "bash": "allow",
}

_WRITE_PERMISSION = {
    "*": "deny",
    "read": "allow",
    "glob": "allow",
    "grep": "allow",
    "lsp": "allow",
    "edit": "allow",
    "external_directory": "deny",
    "task": "deny",
    "skill": "deny",
    "question": "deny",
    "webfetch": "deny",
    "websearch": "deny",
    "doom_loop": "deny",
    "bash": {
        "pwd": "allow",
        "ls *": "allow",
        "find *": "allow",
        "cat *": "allow",
        "head *": "allow",
        "tail *": "allow",
        "sed *": "allow",
        "grep *": "allow",
        "rg *": "allow",
        "git status *": "allow",
        "git diff *": "allow",
        "git log *": "allow",
        "git show *": "allow",
        "git grep *": "allow",
    },
}


class OpenCodeRuntime(BaseCliAgentRuntime):
    runtime_name = "opencode"

    def build_invocation(
        self, request: AgentRequest
    ) -> tuple[list[str], str | None, Mapping[str, str] | None]:
        command = [*self.command_prefix, "run", "--format", "json", "--dir", str(request.cwd.resolve())]
        if request.access == "workspace_write":
            command.append("--auto")
        if self.profile.model:
            command.extend(["--model", self.profile.model])
        if self.profile.effort:
            command.extend(["--variant", self.profile.effort])
        command.extend(self.profile.extra_args)
        command.append(stage_prompt(request.entry_file))
        env = os.environ.copy()
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps(
            {"permission": _READ_ONLY_PERMISSION if request.access == "read_only" else _WRITE_PERMISSION},
            separators=(",", ":"),
        )
        return command, None, env

    def parse_result(
        self, request: AgentRequest, command: list[str], process: ProcessResult
    ) -> AgentRunResult:
        events = parse_json_lines(process.stdout)
        session_id: str | None = None
        final_text: str | None = None
        usage: dict[str, object] = {}
        cost_usd: float | None = None
        for event in events:
            session_id = session_id or first_string((
                event.get("sessionID"),
                event.get("sessionId"),
                event.get("session_id"),
                nested_get(event, "session", "id"),
            ))
            part = event.get("part")
            if isinstance(part, dict):
                text = first_string((part.get("text"), part.get("content")))
                if text:
                    final_text = text
            text = first_string((event.get("text"), event.get("content"), event.get("message")))
            if text:
                final_text = text
            event_usage = event.get("tokens") or event.get("usage")
            if isinstance(event_usage, dict):
                usage.update(event_usage)
            value = event.get("cost")
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cost_usd = float(value)
        structured: object | None = None
        if final_text and request.output_schema is not None:
            try:
                structured = json.loads(final_text)
            except json.JSONDecodeError:
                pass
        return AgentRunResult(
            status=self.status(process),
            exit_code=process.exit_code,
            session_id=session_id,
            structured_output=structured,
            final_text=final_text,
            usage=usage,
            cost_usd=cost_usd,
            events=events,
            stderr=process.stderr,
            duration_seconds=process.duration_seconds,
            command=tuple(command),
        )
