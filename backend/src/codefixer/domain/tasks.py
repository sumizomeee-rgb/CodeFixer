from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TaskStatus = Literal['awaiting_start', 'queued', 'running', 'cancel_requested', 'completed', 'failed', 'canceled']
TaskResult = Literal['changed', 'no_change']
RunStatus = Literal['queued', 'running', 'superseded', 'completed', 'failed', 'canceled']


@dataclass(frozen=True)
class IngestedTicket:
    provider_instance_id: str
    external_ticket_id: str
    title: str
    payload: dict[str, object]
    external_version: str | None = None
    eligible: bool = True
