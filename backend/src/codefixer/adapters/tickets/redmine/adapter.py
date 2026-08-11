from __future__ import annotations

from typing import Any, Callable

import httpx

from codefixer.application.ports.tickets import TicketBatch
from codefixer.domain.tasks import IngestedTicket

SecretGetter = Callable[[str], str | None]


class RedmineTicketProvider:
    def __init__(
        self,
        config: dict[str, Any],
        get_secret: SecretGetter,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.provider_id = str(config["id"])
        api_key_ref = str(config.get("apiKeySecretRef", ""))
        api_key = get_secret(api_key_ref) if api_key_ref else None
        if not api_key:
            raise ValueError(f"missing Redmine API key secret: {api_key_ref}")
        base_url = str(config.get("baseUrl", "")).rstrip("/")
        if not base_url:
            raise ValueError("Redmine baseUrl is required")
        self.client = client or httpx.Client(
            base_url=base_url,
            headers={"X-Redmine-API-Key": api_key, "Accept": "application/json"},
            timeout=30.0,
        )
        self._closed_status_ids: set[int] | None = None

    def _get(self, path: str, params: dict[str, object] | None = None) -> dict[str, Any]:
        response = self.client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("Redmine response root must be object")
        return payload

    def test_connection(self) -> dict[str, object]:
        payload = self._get("/issues.json", {"limit": 1, "status_id": "*"})
        return {"ready": isinstance(payload.get("issues"), list), "providerId": self.provider_id}

    def _closed_statuses(self) -> set[int]:
        if self._closed_status_ids is None:
            payload = self._get("/issue_statuses.json")
            values = payload.get("issue_statuses") or []
            self._closed_status_ids = {
                int(item["id"])
                for item in values
                if isinstance(item, dict) and item.get("is_closed") is True
            }
        return self._closed_status_ids

    def _detail(self, issue_id: int) -> dict[str, Any]:
        payload = self._get(
            f"/issues/{issue_id}.json",
            {"include": "journals,attachments,relations,changesets"},
        )
        issue = payload.get("issue")
        if not isinstance(issue, dict):
            raise ValueError(f"Redmine issue detail missing for {issue_id}")
        return issue

    def poll(self, cursor: str | None) -> TicketBatch:
        offset = 0
        limit = 100
        summaries: list[dict[str, Any]] = []
        while True:
            params: dict[str, object] = {
                "status_id": "*",
                "limit": limit,
                "offset": offset,
                "sort": "updated_on,id",
            }
            if self.config.get("projectId") is not None:
                params["project_id"] = self.config["projectId"]
            if self.config.get("trackerId") is not None:
                params["tracker_id"] = self.config["trackerId"]
            if cursor:
                params["updated_on"] = f">={cursor}"
            payload = self._get("/issues.json", params)
            page = payload.get("issues") or []
            if not isinstance(page, list):
                raise ValueError("Redmine issues must be list")
            summaries.extend(item for item in page if isinstance(item, dict))
            total = int(payload.get("total_count", len(summaries)))
            offset += len(page)
            if not page or offset >= total:
                break
        closed = self._closed_statuses()
        tickets: list[IngestedTicket] = []
        newest = cursor
        for summary in summaries:
            issue_id = int(summary["id"])
            issue = self._detail(issue_id)
            updated = str(issue.get("updated_on") or summary.get("updated_on") or "")
            if newest is None or updated > newest:
                newest = updated
            status = issue.get("status") if isinstance(issue.get("status"), dict) else {}
            status_id = int(status.get("id", 0))
            external_id = str(issue_id)
            payload: dict[str, object] = {
                "provider": "redmine",
                "providerInstanceId": self.provider_id,
                "externalTicketId": external_id,
                "url": f"{str(self.client.base_url).rstrip('/')}/issues/{external_id}",
                "title": str(issue.get("subject", "")),
                "description": issue.get("description"),
                "project": issue.get("project"),
                "tracker": issue.get("tracker"),
                "status": issue.get("status"),
                "priority": issue.get("priority"),
                "version": issue.get("fixed_version"),
                "comments": issue.get("journals") or [],
                "attachments": issue.get("attachments") or [],
                "relations": issue.get("relations") or [],
                "changesets": issue.get("changesets") or [],
                "raw": issue,
            }
            tickets.append(
                IngestedTicket(
                    self.provider_id,
                    external_id,
                    str(issue.get("subject", "")),
                    payload,
                    updated or None,
                    status_id not in closed,
                )
            )
        return TicketBatch(tickets=tickets, next_cursor=newest, raw_count=len(summaries))
