from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from codefixer.adapters.agents import build_agent_runtime
from codefixer.application.ports.agents import AgentAccess, AgentRequest
from codefixer.infrastructure.process_runner import ProcessResult


class FakeRunner:
    def __init__(self, result: ProcessResult):
        self.result = result
        self.calls: list[dict[str, object]] = []

    def run(self, command, *, cwd, stdin_text, env, timeout_seconds):
        self.calls.append({"command": command, "cwd": cwd, "stdin": stdin_text, "env": env, "timeout": timeout_seconds})
        return self.result


def fixture_files(tmp_path: Path) -> tuple[Path, Path, Path]:
    cwd = tmp_path / "repo"; cwd.mkdir()
    entry = tmp_path / "entry.md"; entry.write_text("# Stage entry\nRead the ticket archive.\n", encoding="utf-8")
    schema = tmp_path / "result.schema.json"; schema.write_text(json.dumps({"type":"object","required":["ok"],"properties":{"ok":{"type":"boolean"}}}), encoding="utf-8")
    return cwd, entry, schema


def request(tmp_path: Path, access: str = "read_only") -> AgentRequest:
    cwd, entry, schema = fixture_files(tmp_path)
    return AgentRequest(stage="discovery", entry_file=entry, cwd=cwd, access=cast(AgentAccess, access), output_schema=schema)


def test_claude_uses_print_json_schema_and_stage_permission(tmp_path: Path):
    runner = FakeRunner(ProcessResult(0, json.dumps({"session_id":"c1","structured_output":{"ok":True},"usage":{"input_tokens":10},"total_cost_usd":0.02}), "", False, 1.2))
    runtime = build_agent_runtime({"id":"discover","runtime":"claudeCode","executableRef":"claude","model":"sonnet"},{"claude":{"command":["claude"]}},runner=runner)
    result = runtime.run(request(tmp_path)); command=runner.calls[0]["command"]
    assert isinstance(command,list); assert command[:3]==["claude","--bare","-p"]; assert "--output-format" in command and "json" in command
    assert command[command.index("--permission-mode")+1]=="dontAsk"; assert command[command.index("--tools")+1]=="Read,Glob,Grep,Bash"
    allowed_index=command.index("--allowedTools"); assert command[allowed_index+1:allowed_index+4]==["Read","Glob","Grep"]
    assert "bypassPermissions" not in command; assert "--json-schema" in command; assert result.structured_output=={"ok":True}; assert result.session_id=="c1"


def test_claude_translates_draft_2020_schema_metadata(tmp_path: Path):
    cwd, entry, schema = fixture_files(tmp_path)
    schema.write_text(json.dumps({"$schema":"https://json-schema.org/draft/2020-12/schema","type":"object","$defs":{"answer":{"type":"boolean"}},"properties":{"ok":{"$ref":"#/$defs/answer"}}}),encoding="utf-8")
    runner=FakeRunner(ProcessResult(0,json.dumps({"structured_output":{"ok":True}}),"",False,.2));runtime=build_agent_runtime({"id":"discover","runtime":"claudeCode","executableRef":"claude"},{"claude":{"command":["claude"]}},runner=runner)
    runtime.run(AgentRequest(stage="discovery",entry_file=entry,cwd=cwd,access="read_only",output_schema=schema));command=runner.calls[0]["command"]
    assert isinstance(command,list);translated=json.loads(command[command.index("--json-schema")+1]);assert "$schema" not in translated;assert "definitions" in translated;assert translated["properties"]["ok"]["$ref"]=="#/definitions/answer"


def test_claude_repair_allows_file_edits_but_not_unrestricted_shell(tmp_path: Path):
    runner=FakeRunner(ProcessResult(0,json.dumps({"structured_output":{"ok":True}}),"",False,.2));runtime=build_agent_runtime({"id":"repair","runtime":"claudeCode","executableRef":"claude"},{"claude":{"command":["claude"]}},runner=runner)
    runtime.run(request(tmp_path,"workspace_write"));command=runner.calls[0]["command"];assert isinstance(command,list);assert command[command.index("--tools")+1]=="Read,Glob,Grep,Bash,Edit,Write";allowed=command[command.index("--allowedTools")+1:];assert "Edit" in allowed and "Write" in allowed and "Bash" not in allowed


def test_codex_uses_exec_json_stdin_and_native_sandbox(tmp_path: Path):
    stdout="\n".join([json.dumps({"type":"thread.started","thread_id":"t1"}),json.dumps({"type":"item.completed","item":{"type":"agent_message","text":'{"ok":true}'}}),json.dumps({"type":"turn.completed","usage":{"input_tokens":12,"output_tokens":3}})])
    runner=FakeRunner(ProcessResult(0,stdout,"",False,.8));runtime=build_agent_runtime({"id":"repair","runtime":"codex","executableRef":"codex","model":"gpt-5.3-codex","effort":"high"},{"codex":{"command":["codex"]}},runner=runner);req=request(tmp_path,"workspace_write");result=runtime.run(req);call=runner.calls[0];command=call["command"]
    assert isinstance(command,list);assert command[:3]==["codex","exec","--json"];assert command[command.index("--sandbox")+1]=="workspace-write";assert command[-1]=="-";assert isinstance(call["stdin"],str) and str(req.entry_file.resolve()) in call["stdin"];assert result.session_id=="t1";assert result.structured_output=={"ok":True}


def test_codex_stage_schemas_use_supported_strict_subset():
    artifact_root = Path(__file__).resolve().parents[3] / "contracts" / "artifacts"
    forbidden = {"allOf", "if", "then", "else", "uniqueItems"}

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            assert not forbidden.intersection(value)
            if "const" in value or "enum" in value:
                assert "type" in value
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    for name in ("scope-discovery", "task-discovery", "repair-result", "review", "no-change-report"):
        inspect(json.loads((artifact_root / f"{name}.schema.json").read_text(encoding="utf-8")))


def test_opencode_does_not_use_dash_p_and_injects_permissions(tmp_path: Path):
    stdout="\n".join([json.dumps({"type":"session","sessionID":"o1"}),json.dumps({"type":"text","part":{"text":'{"ok":true}'},"cost":.01})]);runner=FakeRunner(ProcessResult(0,stdout,"",False,.4));runtime=build_agent_runtime({"id":"review","runtime":"opencode","executableRef":"opencode","model":"anthropic/claude-sonnet"},{"opencode":{"command":["opencode"]}},runner=runner);result=runtime.run(request(tmp_path));call=runner.calls[0];command=call["command"]
    assert isinstance(command,list);assert command[:4]==["opencode","run","--format","json"];assert "-p" not in command and "--auto" not in command;env=call["env"];assert isinstance(env,dict);inline=json.loads(env["OPENCODE_CONFIG_CONTENT"]);assert inline["permission"]["edit"]=="deny" and inline["permission"]["external_directory"]=="deny";assert result.session_id=="o1"


def test_opencode_repair_denies_external_and_network_while_allowing_edit(tmp_path: Path):
    runner=FakeRunner(ProcessResult(0,json.dumps({"type":"text","part":{"text":'{"ok":true}'}}),"",False,.2));runtime=build_agent_runtime({"id":"repair","runtime":"opencode","executableRef":"opencode"},{"opencode":{"command":["opencode"]}},runner=runner);runtime.run(request(tmp_path,"workspace_write"));call=runner.calls[0];command=call["command"];assert isinstance(command,list) and "--auto" in command;env=call["env"];assert isinstance(env,dict);permission=json.loads(env["OPENCODE_CONFIG_CONTENT"])["permission"];assert permission["*"]=="deny" and permission["edit"]=="allow" and permission["external_directory"]=="deny" and permission["webfetch"]=="deny" and permission["task"]=="deny"


def test_timeout_is_normalized(tmp_path: Path):
    runner=FakeRunner(ProcessResult(-9,"","timeout",True,15.0));runtime=build_agent_runtime({"id":"review","runtime":"codex","executableRef":"codex"},{"codex":{"command":["codex"]}},runner=runner);result=runtime.run(request(tmp_path));assert result.status=="timed_out" and result.exit_code==-9


def test_profile_requires_known_runtime_and_binding():
    with pytest.raises(ValueError,match="unsupported agent runtime"):build_agent_runtime({"id":"x","runtime":"unknown","executableRef":"x"},{"x":{"command":["x"]}})
    with pytest.raises(ValueError):build_agent_runtime({"id":"x","runtime":"codex","executableRef":"missing"},{})
