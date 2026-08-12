from __future__ import annotations

import hashlib
from dataclasses import dataclass

from codefixer.application.ports.sources import ModificationSourceAdapter
from codefixer.application.ports.tickets import TicketProvider
from codefixer.infrastructure.config_store import canonical_json


@dataclass(frozen=True)
class StabilityCheckResult:
    ready: bool
    code: str | None
    summary: str
    detail: dict[str, object]


class PreDeliveryStabilityGuard:
    def __init__(self, ticket_provider: TicketProvider, source: ModificationSourceAdapter):
        self.ticket_provider = ticket_provider
        self.source = source

    def check(self, *, external_ticket_id: str, frozen_external_version: str | None, frozen_ticket_content_hash: str, frozen_source_revision: str) -> StabilityCheckResult:
        latest = self.ticket_provider.fetch(external_ticket_id)
        latest_hash = hashlib.sha256(canonical_json(latest.payload).encode()).hexdigest()
        detail: dict[str, object] = {"ticketExternalVersion": latest.external_version, "ticketContentSha256": latest_hash, "sourceRevision": None}
        if not latest.eligible:
            return StabilityCheckResult(False, "ticket_ineligible", "The ticket is no longer eligible for automatic repair", detail)
        if latest.external_version != frozen_external_version or latest_hash != frozen_ticket_content_hash:
            return StabilityCheckResult(False, "ticket_changed_during_run", "The ticket changed after this TaskRun froze its input snapshot", detail)
        current_revision = self.source.current_revision()
        detail["sourceRevision"] = current_revision
        if current_revision != frozen_source_revision:
            return StabilityCheckResult(False, "base_changed_conflict", "The modification source baseline changed before delivery", detail)
        return StabilityCheckResult(True, None, "Ticket and source baseline are stable", detail)
