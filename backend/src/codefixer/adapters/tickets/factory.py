from __future__ import annotations

from typing import Any, Callable

import httpx

from codefixer.adapters.tickets.redmine import RedmineTicketProvider
from codefixer.adapters.tickets.tapd import TapdTicketProvider
from codefixer.application.ports.tickets import TicketProvider


def build_ticket_provider(
    config: dict[str, Any],
    get_secret: Callable[[str], str | None],
    client: httpx.Client | None = None,
) -> TicketProvider:
    provider_type = str(config.get("type", ""))
    if provider_type == "redmine":
        return RedmineTicketProvider(config, get_secret, client)
    if provider_type == "tapd":
        return TapdTicketProvider(config, get_secret, client)
    raise ValueError(f"unsupported ticket provider type: {provider_type}")
