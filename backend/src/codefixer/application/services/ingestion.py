from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any

import httpx

from codefixer.adapters.tickets.factory import build_ticket_provider
from codefixer.application.ports.tickets import TicketBatch, TicketProvider
from codefixer.application.services.routing import route_ticket
from codefixer.infrastructure.task_store import TaskStore


class IngestionService:
    def __init__(
        self,
        connection: sqlite3.Connection,
        projects: list[dict[str, Any]],
        execution_mode: str,
    ) -> None:
        self.store = TaskStore(connection)
        self.projects = projects
        self.execution_mode = execution_mode

    def ingest_batch(self, provider_id: str, batch: TicketBatch) -> dict[str, object]:
        matched = 0
        failed_route = 0
        ignored_before_intake = 0
        ignored_by_version = 0
        ignored_by_title = 0
        task_ids: list[str] = []
        for ticket in batch.tickets:
            if ticket.provider_instance_id != provider_id:
                raise ValueError("provider batch contains foreign ticket")
            route = route_ticket(ticket, self.projects)
            if route.kind == "ignored_before_intake":
                ignored_before_intake += 1
                continue
            if route.kind == "ignored_by_version":
                ignored_by_version += 1
                continue
            if route.kind == "ignored_by_title":
                ignored_by_title += 1
                continue
            if route.kind == "matched":
                matched += 1
            else:
                failed_route += 1
            task = self.store.ingest(
                ticket,
                route.project_id,
                self.execution_mode,
                route.failure,
            )
            task_ids.append(str(task["id"]))
        self.store.set_cursor(provider_id, batch.next_cursor)
        return {
            "providerId": provider_id,
            "rawCount": batch.raw_count,
            "ingested": len(task_ids),
            "ignoredBeforeIntake": ignored_before_intake,
            "ignoredByVersion": ignored_by_version,
            "ignoredByTitle": ignored_by_title,
            "matched": matched,
            "routingFailed": failed_route,
            "nextCursor": batch.next_cursor,
            "taskIds": task_ids,
        }

def poll_configured_provider(
    connection: sqlite3.Connection,
    provider_config: dict[str, Any],
    projects: list[dict[str, Any]],
    execution_mode: str,
    get_secret: Callable[[str], str | None],
    client: httpx.Client | None = None,
) -> dict[str, object]:
    provider: TicketProvider = build_ticket_provider(provider_config, get_secret, client)
    store = TaskStore(connection)
    cursor = store.get_cursor(provider.provider_id)
    batch = provider.poll(cursor)
    return IngestionService(connection, projects, execution_mode).ingest_batch(
        provider.provider_id, batch
    )
