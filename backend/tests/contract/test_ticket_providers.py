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
            return httpx.Response(200, json={"issue": {"id": 7, "subject": "A", "description": "detail", "created_on": "2026-08-10T00:00:00Z", "updated_on": "2026-08-12T00:00:00Z", "status": {"id": 1, "name": "New"}, "journals": [{"id": 2, "notes": "comment"}], "attachments": [{"id": 3, "filename": "a.log"}], "relations": [{"id": 4}], "changesets": [{"revision": "abc"}]}})
        raise AssertionError(request.url)

    client = httpx.Client(base_url="https://redmine.example", transport=httpx.MockTransport(handler), headers={"X-Redmine-API-Key": "key-value"})
    provider = RedmineTicketProvider({"id": "rm", "type": "redmine", "baseUrl": "https://redmine.example", "apiKeySecretRef": "rm-key"}, lambda key: "key-value" if key == "rm-key" else None, client)
    batch = provider.poll("2026-08-11T00:00:00Z")
    assert batch.next_cursor == "2026-08-12T00:00:00Z"
    assert len(batch.tickets) == 1
    ticket = batch.tickets[0]
    assert ticket.eligible is True
    assert ticket.payload["createdAt"] == "2026-08-10T00:00:00Z"
    assert ticket.payload["comments"] == [{"id": 2, "notes": "comment"}]
    list_request = next(request for request in seen if request.url.path == "/issues.json")
    assert list_request.url.params["updated_on"] == ">=2026-08-11T00:00:00Z"


def test_redmine_provider__lists_versions_from_project_catalog():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/projects/client/versions.json"
        return httpx.Response(
            200,
            json={
                "versions": [
                    {"id": 41, "name": "4.7", "status": "open"},
                    {"id": 42, "name": "4.8", "status": "locked"},
                ]
            },
        )

    client = httpx.Client(base_url="https://redmine.example", transport=httpx.MockTransport(handler))
    provider = RedmineTicketProvider(
        {"id": "rm", "type": "redmine", "baseUrl": "https://redmine.example", "apiKeySecretRef": "rm-key", "projectId": "client"},
        lambda _: "key-value",
        client,
    )
    assert provider.list_versions() == [
        {"id": "41", "name": "4.7"},
        {"id": "42", "name": "4.8"},
    ]


def test_redmine_provider__falls_back_to_visible_issue_versions_when_catalog_is_forbidden():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/projects/client/versions.json":
            return httpx.Response(403, json={"error": "forbidden"})
        if request.url.path == "/issues.json":
            return httpx.Response(
                200,
                json={
                    "issues": [
                        {"id": 7, "project": {"id": "client"}, "fixed_version": {"id": 41, "name": "4.7"}},
                        {"id": 8, "project": {"id": "client"}, "fixed_version": {"id": 41, "name": "4.7"}},
                    ],
                    "total_count": 2,
                },
            )
        raise AssertionError(request.url)

    client = httpx.Client(base_url="https://redmine.example", transport=httpx.MockTransport(handler))
    provider = RedmineTicketProvider(
        {"id": "rm", "type": "redmine", "baseUrl": "https://redmine.example", "apiKeySecretRef": "rm-key", "projectId": "client"},
        lambda _: "key-value",
        client,
    )
    assert provider.list_versions() == [{"id": "41", "name": "4.7"}]


def test_redmine_provider__discovers_version_catalogs_from_visible_issue_projects():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/issues.json":
            return httpx.Response(
                200,
                json={
                    "issues": [{"id": 7, "project": {"id": 12, "name": "Client"}}],
                    "total_count": 1,
                },
            )
        if request.url.path == "/projects/12/versions.json":
            return httpx.Response(
                200,
                json={"versions": [{"id": 41, "name": "4.7"}, {"id": 42, "name": "4.8"}]},
            )
        raise AssertionError(request.url)

    client = httpx.Client(base_url="https://redmine.example", transport=httpx.MockTransport(handler))
    provider = RedmineTicketProvider(
        {"id": "rm", "type": "redmine", "baseUrl": "https://redmine.example", "apiKeySecretRef": "rm-key"},
        lambda _: "key-value",
        client,
    )
    assert provider.list_versions() == [
        {"id": "41", "name": "4.7"},
        {"id": "42", "name": "4.8"},
    ]


def test_tapd_provider__supports_basic_auth_and_freezes_related_evidence():
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/bugs":
            return httpx.Response(200, json={"status": 1, "data": [{"Bug": {"id": "1010000000000000001", "title": "B", "description": "detail", "status": "in_progress", "module": "商城", "created": "2026-08-10 01:00:00", "modified": "2026-08-12 01:00:00", "closed": None}}]})
        if request.url.path == "/comments":
            return httpx.Response(200, json={"status": 1, "data": [{"Comment": {"id": "c1", "description": "note"}}]})
        if request.url.path == "/attachments":
            return httpx.Response(200, json={"status": 1, "data": [{"Attachment": {"id": "a1", "filename": "x.png"}}]})
        if request.url.path == "/bug_changes":
            return httpx.Response(200, json={"status": 1, "data": [{"BugChange": {"id": "h1", "field": "status"}}]})
        if request.url.path == "/bugs/get_link_bugs":
            return httpx.Response(200, json={"status": 1, "data": [{"id": "1010000000000000002", "type": "direct_relate"}]})
        if request.url.path == "/iterations":
            return httpx.Response(200, json={"status": 1, "data": []})
        raise AssertionError(request.url)

    client = httpx.Client(base_url="https://api.tapd.cn", transport=httpx.MockTransport(handler), auth=httpx.BasicAuth("u", "p"))
    provider = TapdTicketProvider({"id": "tapd", "type": "tapd", "workspaceId": "101", "auth": {"mode": "basic", "usernameSecretRef": "u", "passwordSecretRef": "p"}}, lambda key: {"u": "u", "p": "p"}.get(key), client)
    batch = provider.poll("2026-08-11 00:00:00")
    assert batch.next_cursor == "2026-08-12 01:00:00"
    ticket = batch.tickets[0]
    assert ticket.payload["createdAt"] == "2026-08-10 01:00:00"
    assert ticket.payload["module"] == "商城"
    assert ticket.payload["comments"] == [{"id": "c1", "description": "note"}]
    assert ticket.payload["attachments"] == [{"id": "a1", "filename": "x.png"}]
    assert ticket.payload["changes"] == [{"id": "h1", "field": "status"}]
    assert "/bugs/get_link_bugs" in paths


def test_tapd_provider__uses_intake_cursor_as_server_side_modified_filter():
    seen_modified: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/bugs":
            seen_modified.append(str(request.url.params.get("modified")))
            return httpx.Response(200, json={"status": 1, "data": []})
        if request.url.path == "/iterations":
            return httpx.Response(200, json={"status": 1, "data": []})
        raise AssertionError(request.url)

    client = httpx.Client(base_url="https://api.tapd.cn", transport=httpx.MockTransport(handler))
    provider = TapdTicketProvider(
        {"id": "tapd", "type": "tapd", "workspaceId": "101", "auth": {"mode": "basic"}},
        lambda _: None,
        client,
    )

    provider.poll("2026-08-15T18:53:27+08:00")

    assert seen_modified == [">=2026-08-15 18:53:27"]


def test_tapd_provider__lists_workspace_versions():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/iterations"
        assert request.url.params["workspace_id"] == "101"
        assert request.url.params["status"] == "open"
        return httpx.Response(
            200,
            json={
                "status": 1,
                "data": [
                    {"Iteration": {"id": "i74", "name": "【战双2.0】【v7.4】"}},
                    {"Iteration": {"id": "i49", "name": "【v4.9】正式迭代"}},
                ],
            },
        )

    client = httpx.Client(base_url="https://api.tapd.cn", transport=httpx.MockTransport(handler))
    provider = TapdTicketProvider(
        {"id": "tapd", "type": "tapd", "workspaceId": "101", "auth": {"mode": "basic"}},
        lambda key: {"": None}.get(key),
        client,
    )
    assert provider.list_versions() == [
        {"id": "7.4", "name": "7.4"},
        {"id": "4.9", "name": "4.9"},
    ]


def test_tapd_provider__infers_requirement_version_like_haru_analyze():
    assert TapdTicketProvider._requirement_version(
        {"title": "【战双兄弟2.0】【v4.7、trunk】修复", "version_report": "4.8review"},
        "【v4.9】当前迭代",
    ) == "4.7"
