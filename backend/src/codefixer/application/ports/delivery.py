from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class FrozenDeliveryContext:
    task_id: str
    run_id: str
    change_version: int
    source_id: str
    base_revision: str
    patch_path: Path
    patch_sha256: str
    manifest_path: Path


@dataclass(frozen=True)
class FinalActionResult:
    action_id: str
    action_type: str
    status: str
    outcome: str
    detail: dict[str, object]

    @property
    def succeeded(self) -> bool:
        return self.status == "succeeded"


class FinalAction(Protocol):
    action_id: str
    action_type: str

    def execute(self, context: FrozenDeliveryContext) -> FinalActionResult: ...
