from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from codefixer.application.services.preflight import _writable_directory


def test_writable_directory_checks_do_not_collide_when_preflights_overlap(
    tmp_path: Path,
) -> None:
    target = tmp_path / "fallback-patches" / "pipeline-demo"

    with ThreadPoolExecutor(max_workers=32) as pool:
        results = list(pool.map(_writable_directory, [target] * 256))

    assert all(results)
    assert list(target.glob(".codefixer-preflight-*")) == []
