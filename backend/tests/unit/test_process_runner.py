from __future__ import annotations

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
