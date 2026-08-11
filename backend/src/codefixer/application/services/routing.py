from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from codefixer.domain.tasks import IngestedTicket

RouteKind = Literal["matched", "not_found", "ambiguous"]


@dataclass(frozen=True)
class RouteDecision:
    kind: RouteKind
    project_id: str | None
    failure: dict[str, object] | None = None


def _field(payload: dict[str, object], path: str) -> object | None:
    current: object = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _condition_matches(payload: dict[str, object], condition: dict[str, Any]) -> bool:
    field = str(condition.get("field", ""))
    op = str(condition.get("operator", "eq"))
    expected = condition.get("value")
    actual = _field(payload, field)
    if op == "exists":
        return actual is not None
    if op == "eq":
        return actual == expected
    if op == "neq":
        return actual != expected
    if op == "contains":
        return isinstance(actual, str) and str(expected) in actual
    if op == "in":
        return isinstance(expected, list) and actual in expected
    raise ValueError(f"unsupported routing operator: {op}")


def route_ticket(ticket: IngestedTicket, projects: list[dict[str, Any]]) -> RouteDecision:
    candidates: list[tuple[int, str, str]] = []
    for project in projects:
        project_id = str(project.get("id", "")).strip()
        if not project_id or project.get("enabled", True) is False:
            continue
        for rule in project.get("routingRules") or []:
            if str(rule.get("providerRef", "")) != ticket.provider_instance_id:
                continue
            conditions = rule.get("conditions") or []
            if rule.get("catchAll") is True or all(
                _condition_matches(ticket.payload, condition) for condition in conditions
            ):
                candidates.append(
                    (int(rule.get("priority", 0)), project_id, str(rule.get("id", "route")))
                )
    if not candidates:
        return RouteDecision(
            "not_found",
            None,
            {
                "code": "project_not_found",
                "stage": "ingest",
                "summary": "没有项目路由规则匹配该工单",
                "retryable": False,
                "suggested_action": "检查项目 routingRules 或工单来源配置",
            },
        )
    top_priority = max(item[0] for item in candidates)
    top = [item for item in candidates if item[0] == top_priority]
    unique_projects = sorted({item[1] for item in top})
    if len(unique_projects) != 1:
        return RouteDecision(
            "ambiguous",
            None,
            {
                "code": "project_ambiguous",
                "stage": "ingest",
                "summary": "多个最高优先级项目同时匹配该工单",
                "retryable": False,
                "suggested_action": "调整 routingRules 的优先级或条件使结果唯一",
                "projects": unique_projects,
            },
        )
    return RouteDecision("matched", unique_projects[0])
