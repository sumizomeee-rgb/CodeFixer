from __future__ import annotations

from typing import Any, cast

from codefixer.adapters.agents.claude import ClaudeCodeRuntime
from codefixer.adapters.agents.codex import CodexRuntime
from codefixer.adapters.agents.opencode import OpenCodeRuntime
from codefixer.application.ports.agents import AgentProfile, AgentRuntime, AgentRuntimeName
from codefixer.infrastructure.process_runner import ProcessRunner


def parse_agent_profile(raw: dict[str, Any]) -> AgentProfile:
    profile_id = str(raw.get("id", "")).strip()
    runtime = str(raw.get("runtime", raw.get("type", ""))).strip()
    executable_ref = str(raw.get("executableRef", "")).strip()
    if not profile_id:
        raise ValueError("agent profile id is required")
    if runtime not in {"claudeCode", "codex", "opencode"}:
        raise ValueError(f"unsupported agent runtime: {runtime}")
    if not executable_ref:
        raise ValueError("agent profile executableRef is required")
    extra_args_raw = raw.get("extraArgs") or []
    if not isinstance(extra_args_raw, list) or not all(isinstance(item, str) for item in extra_args_raw):
        raise ValueError("agent profile extraArgs must be string array")
    timeout = int(raw.get("timeoutSeconds", 1800))
    if timeout < 1:
        raise ValueError("agent profile timeoutSeconds must be positive")
    budget_raw = raw.get("maxBudgetUsd")
    budget = float(budget_raw) if budget_raw is not None else None
    return AgentProfile(
        id=profile_id,
        runtime=cast(AgentRuntimeName, runtime),
        executable_ref=executable_ref,
        model=str(raw["model"]) if raw.get("model") else None,
        effort=str(raw["effort"]) if raw.get("effort") else None,
        timeout_seconds=timeout,
        max_budget_usd=budget,
        extra_args=tuple(extra_args_raw),
    )


def build_agent_runtime(
    profile_raw: dict[str, Any],
    executable_bindings: dict[str, dict[str, Any]],
    *,
    runner: ProcessRunner | None = None,
) -> AgentRuntime:
    profile = parse_agent_profile(profile_raw)
    binding = executable_bindings.get(profile.executable_ref)
    command = binding.get("command") if isinstance(binding, dict) else None
    if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
        raise ValueError(f"agent executable binding command is invalid: {profile.executable_ref}")
    if profile.runtime == "claudeCode":
        return ClaudeCodeRuntime(profile, command, runner)
    if profile.runtime == "codex":
        return CodexRuntime(profile, command, runner)
    return OpenCodeRuntime(profile, command, runner)
