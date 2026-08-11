from codefixer.application.services.routing import route_ticket
from codefixer.domain.tasks import IngestedTicket


def _ticket() -> IngestedTicket:
    return IngestedTicket("tapd-main", "1", "商城 Bug", {"workspaceId": "101", "module": "商城", "title": "红点未刷新"})


def test_route_ticket__chooses_unique_highest_priority_project():
    projects = [
        {"id": "generic", "routingRules": [{"id": "all", "providerRef": "tapd-main", "priority": 10, "catchAll": True}]},
        {"id": "shop", "routingRules": [{"id": "shop", "providerRef": "tapd-main", "priority": 50, "conditions": [{"field": "module", "operator": "eq", "value": "商城"}]}]},
    ]
    result = route_ticket(_ticket(), projects)
    assert result.kind == "matched"
    assert result.project_id == "shop"


def test_route_ticket__fails_when_top_priority_is_ambiguous():
    projects = [
        {"id": "a", "routingRules": [{"providerRef": "tapd-main", "priority": 1, "catchAll": True}]},
        {"id": "b", "routingRules": [{"providerRef": "tapd-main", "priority": 1, "catchAll": True}]},
    ]
    result = route_ticket(_ticket(), projects)
    assert result.kind == "ambiguous"
    assert result.failure is not None
    assert result.failure["code"] == "project_ambiguous"
