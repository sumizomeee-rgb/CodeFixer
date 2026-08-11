from __future__ import annotations

import httpx

from codefixer.adapters.tickets.redmine import RedmineTicketProvider
from codefixer.adapters.tickets.tapd import TapdTicketProvider


def test_redmine_provider__freezes_full_issue_and_uses_incremental_filter():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path == "/issues.json":
            return httpx.Response(200, json={"issues": [{"id": 7, "subject": "A", "updated_on": "2026-08-12T00:00:00Z"}], "total_count": 1})
        if request.url.path == "/issue_statuses.json":
            return httpx.Response(200, json={"issue_statuses": [{"id": 1, "name": "New", "is_closed": False}]})
        if request.url.path == "/issues/7.json":
            return httpx.Response(200, json={"issue": {"id": 7, "subject": "A", "description": "detail", "updated_on": "2026-08-12T00:00:00Z", "status": {"id": 1, "name": "New"}, "journals": [{"id": 2, "notes": "comment"}], "attachments": [{"id": 3, "filename": "a.log"}], "relations": [{"id": 4}], "changesets": [{"revision": "abc"}]}})
        raise AssertionError(request.url)

    client = httpx.Client(base_url="https://redmine.example", transport=httpx.MockTransport(handler), headers={"X-Redmine-API-Key": "key-value"})
    provider = RedmineTicketProvider({"id": "rm", "type": "redmine", "baseUrl": "https://redmine.example", "apiKeySecretRef": "rm-key"}, lambda key: "key-value" if key == "rm-key" else None, client)
    batch = provider.poll("2026-08-11T00:00:00Z")
    assert batch.next_cursor == "2026-08-12T00:00:00Z"
    assert len(batch.tickets) == 1
    ticket = batch.tickets[0]
    assert ticket.eligible is True
    assert ticket.payload["comments"] == [{"id": 2, "notes": "comment"}]
    list_request = next(request for request in seen if request.url.path == "/issues.json")
    assert list_request.url.params["updated_on"] == ">=2026-08-11T00:00:00Z"


def test_tapd_provider__supports_basic_auth_and_freezes_related_evidence():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/bugs":
            return httpx.Response(200, json={"status": 1, "data": [{"Bug": {"id": "1010000000000000001", "title": "B", "description": "detail", "status": "in_progress", "module": "商城", "modified": "2026-08-12 01:00:00", "closed": None}}]})
        if request.url.path == "/comments":
            return httpx.Response(200, json={"status": 1, "data": [{"Comment": {"id": "c1", "description": "note"}}]})
        if request.url.path == "/attachments":
            return httpx.Response(200, json={"status": 1, "data": [{"Attachment": {"id": "a1", "filename": "x.png"}}]})
        if request.url.path == "/bug_changes":
            return httpx.Response(200, json={"status": 1, "data": [{"BugChange": {"id": "h1", "field": "status"}}]})
        if request.url.path == "/bugs/get_link_bugs":
            return httpx.Response(200, json={"status": 1, "data": [{"id": "1010000000000000002", "type": "direct_relate"}]})
        raise AssertionError(request.url)

    client = httpx.Client(base_url="https://api.tapd.cn", transport=httpx.MockTransport(handler), auth=httpx.BasicAuth("u", "p"))
    provider = TapdTicketProvider({"id": "tapd", "type": "tapd", "workspaceId": "101", "auth": {"mode": "basic", "usernameSecretRef": "u", "passwordSecretRef": "p"}}, lambda key: {"u": "u", "p": "p"}.get(key), client)
    batch = provider.poll("2026-08-11 00:00:00")
    assert batch.next_cursor == "2026-08-12 01:00:00"
    ticket = batch.tickets[0]
    assert ticket.payload["module"] == "商城"
    assert ticket.payload["comments"] == [{"id": "c1", "description": "note"}]
    assert ticket.payload["attachments"] == [{"id": "a1", "filename": "x.png"}]
    assert ticket.payload["changes"] == [{"id": "h1", "field": "status"}]
    assert "/bugs/get_link_bugs" in paths
