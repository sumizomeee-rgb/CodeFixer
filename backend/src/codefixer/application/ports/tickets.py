from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from codefixer.domain.tasks import IngestedTicket


@dataclass(frozen=True)
class TicketBatch:
    tickets: list[IngestedTicket]
    next_cursor: str | None
    raw_count: int


class TicketProvider(Protocol):
    provider_id: str

    def test_connection(self) -> dict[str, object]: ...

    def list_versions(self) -> list[dict[str, str]]: ...

    def poll(self, cursor: str | None) -> TicketBatch: ...
