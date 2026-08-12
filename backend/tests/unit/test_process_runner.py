from __future__ import annotations

import os
import sys
from pathlib import Path

from codefixer.infrastructure.process_runner import SubprocessRunner


def test_process_runner_preserves_child_output_line_endings(tmp_path: Path) -> None:
    result = SubprocessRunner().run(
        [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'a\\r\\nb\\n')"],
        cwd=tmp_path,
        stdin_text=None,
        env=None,
        timeout_seconds=10,
    )

    assert result.exit_code == 0
    assert result.stdout == "a\r\nb\n"


def test_process_runner_executes_windows_cmd_shim_from_path(tmp_path: Path) -> None:
    if os.name != "nt":
        return
    shim = tmp_path / "codefixer-shim.cmd"
    shim.write_text("@echo off\r\necho shim:%~1\r\n", encoding="utf-8")
    env = {"PATH": f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}"}

    result = SubprocessRunner().run(
        ["codefixer-shim", "works"],
        cwd=tmp_path,
        stdin_text=None,
        env=env,
        timeout_seconds=10,
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "shim:works"


def test_process_runner_resolves_direct_native_cmd_proxy(tmp_path: Path) -> None:
    target = tmp_path / "native.exe"
    target.write_bytes(b"placeholder")
    shim = tmp_path / "agent.cmd"
    shim.write_text('@echo off\r\n"%dp0%\\native.exe" %*\r\n', encoding="utf-8")

    assert SubprocessRunner._native_cmd_proxy(shim) == target
