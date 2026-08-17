from codefixer.application.services.routing import route_ticket
from codefixer.domain.tasks import IngestedTicket


def _ticket() -> IngestedTicket:
    return IngestedTicket("tapd-main", "1", "商城 Bug", {"workspaceId": "101", "module": "商城", "title": "红点未刷新", "createdAt": "2026-08-11T00:00:00Z"})


def test_route_ticket__chooses_unique_highest_priority_project():
    projects = [
        {"id": "generic", "intakeStartedAt": "2026-08-10T00:00:00Z", "routingRules": [{"id": "all", "providerRef": "tapd-main", "priority": 10, "catchAll": True}]},
        {"id": "shop", "intakeStartedAt": "2026-08-10T00:00:00Z", "routingRules": [{"id": "shop", "providerRef": "tapd-main", "priority": 50, "conditions": [{"field": "module", "operator": "eq", "value": "商城"}]}]},
    ]
    result = route_ticket(_ticket(), projects)
    assert result.kind == "matched"
    assert result.project_id == "shop"


def test_route_ticket__fails_when_top_priority_is_ambiguous():
    projects = [
        {"id": "a", "intakeStartedAt": "2026-08-10T00:00:00Z", "routingRules": [{"providerRef": "tapd-main", "priority": 1, "catchAll": True}]},
        {"id": "b", "intakeStartedAt": "2026-08-10T00:00:00Z", "routingRules": [{"providerRef": "tapd-main", "priority": 1, "catchAll": True}]},
    ]
    result = route_ticket(_ticket(), projects)
    assert result.kind == "ambiguous"
    assert result.failure is not None
    assert result.failure["code"] == "project_ambiguous"


def test_route_ticket__ignores_ticket_created_before_pipeline_intake():
    project = {"id": "shop", "intakeStartedAt": "2026-08-12T00:00:00Z", "routingRules": [{"providerRef": "tapd-main", "priority": 1, "catchAll": True}]}
    result = route_ticket(_ticket(), [project])
    assert result.kind == "ignored_before_intake"
    assert result.project_id is None


def test_route_ticket__does_not_fall_back_when_selected_pipeline_is_too_new():
    projects = [
        {"id": "older-fallback", "intakeStartedAt": "2026-08-01T00:00:00Z", "routingRules": [{"providerRef": "tapd-main", "priority": 1, "catchAll": True}]},
        {"id": "selected", "intakeStartedAt": "2026-08-12T00:00:00Z", "routingRules": [{"providerRef": "tapd-main", "priority": 10, "catchAll": True}]},
    ]
    result = route_ticket(_ticket(), projects)
    assert result.kind == "ignored_before_intake"


def test_route_ticket__accepts_selected_tapd_version_by_name():
    ticket = IngestedTicket(
        "tapd-main",
        "1",
        "商城 Bug",
        {"createdAt": "2026-08-11T00:00:00Z", "fixVersion": {"name": "4.7"}},
    )
    project = {
        "id": "shop",
        "intakeStartedAt": "2026-08-10T00:00:00Z",
        "routingRules": [{
            "providerRef": "tapd-main",
            "priority": 1,
            "catchAll": True,
            "versionFilter": {"mode": "selected", "versions": [{"id": "v47", "name": "4.7"}]},
        }],
    }
    assert route_ticket(ticket, [project]).kind == "matched"


def test_route_ticket__ignores_unselected_or_unversioned_tickets():
    project = {
        "id": "shop",
        "intakeStartedAt": "2026-08-10T00:00:00Z",
        "routingRules": [{
            "providerRef": "tapd-main",
            "priority": 1,
            "catchAll": True,
            "versionFilter": {"mode": "selected", "versions": [{"id": "v47", "name": "4.7"}]},
        }],
    }
    unselected = IngestedTicket("tapd-main", "2", "Bug", {"createdAt": "2026-08-11T00:00:00Z", "fixVersion": {"name": "4.8"}})
    unversioned = IngestedTicket("tapd-main", "3", "Bug", {"createdAt": "2026-08-11T00:00:00Z"})
    assert route_ticket(unselected, [project]).kind == "ignored_by_version"
    assert route_ticket(unversioned, [project]).kind == "ignored_by_version"


def test_route_ticket__all_versions_accepts_unversioned_ticket():
    project = {
        "id": "shop",
        "intakeStartedAt": "2026-08-10T00:00:00Z",
        "routingRules": [{"providerRef": "tapd-main", "priority": 1, "catchAll": True, "versionFilter": {"mode": "all", "versions": []}}],
    }
    assert route_ticket(_ticket(), [project]).kind == "matched"


def test_route_ticket__redmine_does_not_fall_back_to_name_when_ids_differ():
    project = {
        "id": "shop",
        "intakeStartedAt": "2026-08-10T00:00:00Z",
        "routingRules": [{
            "providerRef": "redmine-main",
            "priority": 1,
            "catchAll": True,
            "versionFilter": {"mode": "selected", "versions": [{"id": "41", "name": "4.7"}]},
        }],
    }
    ticket = IngestedTicket(
        "redmine-main",
        "4",
        "Bug",
        {"createdAt": "2026-08-11T00:00:00Z", "fixVersion": {"id": 99, "name": "4.7"}},
    )
    assert route_ticket(ticket, [project]).kind == "ignored_by_version"


def test_route_ticket__requires_configured_title_text() -> None:
    project = {
        "id": "shop",
        "intakeStartedAt": "2026-08-10T00:00:00Z",
        "titleContains": "一键",
        "routingRules": [
            {"providerRef": "tapd-main", "priority": 1, "catchAll": True}
        ],
    }
    matching = IngestedTicket(
        "tapd-main",
        "5",
        "【一键养成】品质显示错误",
        {"createdAt": "2026-08-11T00:00:00Z"},
    )
    unrelated = IngestedTicket(
        "tapd-main",
        "6",
        "【公会战】排名显示错误",
        {"createdAt": "2026-08-11T00:00:00Z"},
    )

    assert route_ticket(matching, [project]).kind == "matched"
    assert route_ticket(unrelated, [project]).kind == "ignored_by_title"
