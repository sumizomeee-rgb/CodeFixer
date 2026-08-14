from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any

import httpx

from codefixer.application.ports.tickets import TicketBatch
from codefixer.domain.tasks import IngestedTicket

SecretGetter = Callable[[str], str | None]

_VERSION = re.compile(r"(?<![\d.])[vV]?(?P<major>\d{1,2})\.(?P<minor>\d{1,2})(?![\d.])")
_PREFIXED_VERSION = re.compile(r"(?<![A-Za-z0-9.])[vV](?P<major>\d{1,2})\.(?P<minor>\d{1,2})(?![\d.])")
_TAGGED_VERSION = re.compile(
    r"(?:^|[【\[,，、/])\s*[vV]?(?P<major>\d{1,2})\.(?P<minor>\d{1,2})"
    r"(?=\s*(?:[】\],，、/]|review\b|xf\b|trunk\b))",
    re.IGNORECASE,
)


def _versions_from_text(value: object, pattern: re.Pattern[str]) -> list[str]:
    values = {
        (int(match.group("major")), int(match.group("minor")))
        for match in pattern.finditer(str(value or ""))
        if 1 <= int(match.group("major")) <= 20
    }
    return [f"{major}.{minor}" for major, minor in sorted(values)]


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

    def list_versions(self) -> list[dict[str, str]]:
        iterations = self._paged_objects(
            "/iterations",
            "Iteration",
            {
                "workspace_id": self.workspace_id,
                "status": "open",
                "fields": "id,name,status,startdate,enddate",
            },
        )
        result: list[dict[str, str]] = []
        seen: set[str] = set()
        for iteration in iterations:
            for name in _versions_from_text(iteration.get("name"), _PREFIXED_VERSION):
                if name in seen:
                    continue
                seen.add(name)
                result.append({"id": name, "name": name})
        return sorted(result, key=lambda item: tuple(map(int, item["name"].split("."))), reverse=True)

    def _iteration_names(self) -> dict[str, str]:
        try:
            iterations = self._paged_objects(
                "/iterations",
                "Iteration",
                {"workspace_id": self.workspace_id, "fields": "id,name"},
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {403, 404}:
                return {}
            raise
        return {
            str(item.get("id") or ""): str(item.get("name") or "")
            for item in iterations
            if item.get("id")
        }

    @staticmethod
    def _requirement_version(bug: dict[str, Any], iteration_name: str) -> str | None:
        candidates = _versions_from_text(bug.get("title"), _TAGGED_VERSION)
        candidates.extend(_versions_from_text(bug.get("version_report"), _VERSION))
        candidates.extend(_versions_from_text(iteration_name, _PREFIXED_VERSION))
        return sorted(set(candidates), key=lambda value: tuple(map(int, value.split("."))))[0] if candidates else None

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
        iteration_names = self._iteration_names()
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
            iteration_name = iteration_names.get(str(bug.get("iteration_id") or ""), "")
            requirement_version = self._requirement_version(bug, iteration_name)
            payload: dict[str, object] = {
                "provider": "tapd",
                "providerInstanceId": self.provider_id,
                "externalTicketId": bug_id,
                "workspaceId": self.workspace_id,
                "url": f"https://www.tapd.cn/{self.workspace_id}/bugtrace/bugs/view/{bug_id}",
                "title": str(bug.get("title", "")),
                "createdAt": bug.get("created"),
                "description": bug.get("description"),
                "module": bug.get("module"),
                "status": bug.get("status"),
                "severity": bug.get("severity"),
                "priority": bug.get("priority_label") or bug.get("priority"),
                "versionReport": bug.get("version_report"),
                "versionFix": bug.get("version_fix"),
                "fixVersion": {"name": requirement_version} if requirement_version else None,
                "requirementVersion": requirement_version,
                "iteration": iteration_name or None,
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
