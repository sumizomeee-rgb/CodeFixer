from __future__ import annotations

import json
from typing import Mapping

from codefixer.adapters.agents.base import BaseCliAgentRuntime, first_string, nested_get, parse_json_lines, stage_prompt
from codefixer.application.ports.agents import AgentRequest, AgentRunResult
from codefixer.infrastructure.process_runner import ProcessResult


class CodexRuntime(BaseCliAgentRuntime):
    runtime_name = "codex"

    def build_invocation(
        self, request: AgentRequest
    ) -> tuple[list[str], str | None, Mapping[str, str] | None]:
        command = [*self.command_prefix, "exec", "--json", "--ephemeral", "--color", "never"]
        command.extend(["--sandbox", "read-only" if request.access == "read_only" else "workspace-write"])
        command.extend(["--cd", str(request.cwd.resolve())])
        if self.profile.model:
            command.extend(["--model", self.profile.model])
        if self.profile.effort:
            command.extend(["-c", f'model_reasoning_effort="{self.profile.effort}"'])
        if request.output_schema is not None:
            command.extend(["--output-schema", str(request.output_schema.resolve())])
        command.extend(self.profile.extra_args)
        command.append("-")
        return command, stage_prompt(request.entry_file), None

    def parse_result(
        self, request: AgentRequest, command: list[str], process: ProcessResult
    ) -> AgentRunResult:
        events = parse_json_lines(process.stdout)
        session_id: str | None = None
        final_text: str | None = None
        structured: object | None = None
        usage: dict[str, object] = {}
        for event in events:
            session_id = session_id or first_string(
                (event.get("thread_id"), event.get("session_id"), nested_get(event, "thread", "id"))
            )
            event_usage = event.get("usage")
            if isinstance(event_usage, dict):
                usage.update(event_usage)
            item = event.get("item")
            if isinstance(item, dict):
                text = first_string((item.get("text"), item.get("content"), item.get("message")))
                if text and str(item.get("type", "")) in {"agent_message", "message", "assistant_message"}:
                    final_text = text
            direct = first_string((event.get("text"), event.get("final_output"), event.get("output")))
            if direct:
                final_text = direct
            possible = event.get("structured_output")
            if possible is not None:
                structured = possible
        if structured is None and final_text and request.output_schema is not None:
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
            events=events,
            stderr=process.stderr,
            duration_seconds=process.duration_seconds,
            command=tuple(command),
        )
