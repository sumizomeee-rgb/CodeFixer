from __future__ import annotations

from typing import Any, Callable

import httpx

from codefixer.application.ports.tickets import TicketBatch
from codefixer.domain.tasks import IngestedTicket

SecretGetter = Callable[[str], str | None]


class TapdTicketProvider:
    def __init__(
        self,
        config: dict[str, Any],
        get_secret: SecretGetter,
        client: httpx.Client | None = None,
    ) -> None:
        self.config = config
        self.provider_id = str(config["id"])
        self.workspace_id = str(config.get("workspaceId", ""))
        if not self.workspace_id:
            raise ValueError("TAPD workspaceId is required")
        if client is not None:
            self.client = client
            return
        auth_config = config.get("auth") or {}
        mode = str(auth_config.get("mode", "basic"))
        if mode == "basic":
            username = get_secret(str(auth_config.get("usernameSecretRef", "")))
            password = get_secret(str(auth_config.get("passwordSecretRef", "")))
            if not username or not password:
                raise ValueError("missing TAPD Basic Auth secrets")
            self.client = httpx.Client(
                base_url="https://api.tapd.cn",
                auth=httpx.BasicAuth(username, password),
                headers={"Accept": "application/json"},
                timeout=30.0,
            )
        elif mode == "oauth":
            token = get_secret(str(auth_config.get("tokenSecretRef", "")))
            if not token:
                raise ValueError("missing TAPD OAuth token secret")
            self.client = httpx.Client(
                base_url="https://api.tapd.cn",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                timeout=30.0,
            )
        else:
            raise ValueError(f"unsupported TAPD auth mode: {mode}")

    def _get(self, path: str, params: dict[str, object]) -> dict[str, Any]:
        response = self.client.get(path, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or int(payload.get("status", 0)) != 1:
            raise ValueError(f"TAPD API failure: {payload}")
        return payload

    def test_connection(self) -> dict[str, object]:
        payload = self._get(
            "/bugs", {"workspace_id": self.workspace_id, "limit": 1, "page": 1}
        )
        return {"ready": isinstance(payload.get("data"), list), "providerId": self.provider_id}

    def _paged_objects(
        self, path: str, root_key: str, params: dict[str, object]
    ) -> list[dict[str, Any]]:
        page_no = 1
        values: list[dict[str, Any]] = []
        while True:
            query = dict(params)
            query.update({"limit": 200, "page": page_no})
            payload = self._get(path, query)
            page = payload.get("data") or []
            if not isinstance(page, list):
                raise ValueError(f"TAPD {path} data must be list")
            for wrapper in page:
                if isinstance(wrapper, dict):
                    value = wrapper.get(root_key)
                    if isinstance(value, dict):
                        values.append(value)
            if len(page) < 200:
                break
            page_no += 1
        return values

    def _enrich(self, bug_id: str) -> dict[str, object]:
        common = {"workspace_id": self.workspace_id, "entry_id": bug_id}
        comments = self._paged_objects(
            "/comments", "Comment", {**common, "entry_type": "bug|bug_remark"}
        )
        attachments = self._paged_objects("/attachments", "Attachment", common)
        changes = self._paged_objects(
            "/bug_changes",
            "BugChange",
            {"workspace_id": self.workspace_id, "bug_id": bug_id},
        )
        relations_payload = self._get(
            "/bugs/get_link_bugs",
            {"workspace_id": self.workspace_id, "bug_id": bug_id},
        )
        relations = relations_payload.get("data") or []
        return {
            "comments": comments,
            "attachments": attachments,
            "changes": changes,
            "relations": relations if isinstance(relations, list) else [],
        }

    def poll(self, cursor: str | None) -> TicketBatch:
        bugs = self._paged_objects("/bugs", "Bug", {"workspace_id": self.workspace_id})
        ineligible_statuses = {str(value) for value in self.config.get("ineligibleStatuses", [])}
        tickets: list[IngestedTicket] = []
        newest = cursor
        for bug in bugs:
            modified = str(bug.get("modified") or "")
            if cursor and modified and modified <= cursor:
                continue
            if newest is None or modified > newest:
                newest = modified
            bug_id = str(bug["id"])
            enriched = self._enrich(bug_id)
            payload: dict[str, object] = {
                "provider": "tapd",
                "providerInstanceId": self.provider_id,
                "externalTicketId": bug_id,
                "workspaceId": self.workspace_id,
                "url": f"https://www.tapd.cn/{self.workspace_id}/bugtrace/bugs/view/{bug_id}",
                "title": str(bug.get("title", "")),
                "description": bug.get("description"),
                "module": bug.get("module"),
                "status": bug.get("status"),
                "severity": bug.get("severity"),
                "priority": bug.get("priority_label") or bug.get("priority"),
                "versionReport": bug.get("version_report"),
                "versionFix": bug.get("version_fix"),
                **enriched,
                "raw": bug,
            }
            eligible = not bool(bug.get("closed")) and str(bug.get("status", "")) not in ineligible_statuses
            tickets.append(
                IngestedTicket(
                    self.provider_id,
                    bug_id,
                    str(bug.get("title", "")),
                    payload,
                    modified or None,
                    eligible,
                )
            )
        return TicketBatch(tickets=tickets, next_cursor=newest, raw_count=len(bugs))
