from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from codefixer.domain.tasks import IngestedTicket

RouteKind = Literal[
    "matched",
    "not_found",
    "ambiguous",
    "ignored_before_intake",
    "ignored_by_version",
]


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


def _version_identity(payload: dict[str, object]) -> tuple[str | None, str | None]:
    value: object = payload.get("fixVersion")
    if value is None:
        value = payload.get("versionFix")
    if value is None:
        value = payload.get("version")
    if isinstance(value, dict):
        version_id = str(value.get("id") or "").strip() or None
        name = str(value.get("name") or "").strip() or None
        return version_id, name
    name = str(value or "").strip() or None
    return None, name


def _version_matches(payload: dict[str, object], rule: dict[str, Any]) -> bool:
    version_filter = rule.get("versionFilter")
    if not isinstance(version_filter, dict) or version_filter.get("mode", "all") == "all":
        return True
    selected = version_filter.get("versions") or []
    actual_id, actual_name = _version_identity(payload)
    if actual_id is None and actual_name is None:
        return False
    for item in selected:
        if not isinstance(item, dict):
            continue
        selected_id = str(item.get("id") or "").strip() or None
        selected_name = str(item.get("name") or "").strip() or None
        if actual_id is not None:
            if selected_id == actual_id:
                return True
            continue
        # TAPD 的工单 version_fix 只返回版本名称，因此保留精确名称匹配。
        if actual_name is not None and selected_name == actual_name:
            return True
    return False


def _timestamp(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def route_ticket(ticket: IngestedTicket, projects: list[dict[str, Any]]) -> RouteDecision:
    candidates: list[tuple[int, str, str, datetime | None]] = []
    ticket_created_at = _timestamp(ticket.payload.get("createdAt"))
    provider_rule_seen = False
    version_accepted = False
    for project in projects:
        project_id = str(project.get("id", "")).strip()
        if not project_id or project.get("enabled", True) is False:
            continue
        for rule in project.get("routingRules") or []:
            if str(rule.get("providerRef", "")) != ticket.provider_instance_id:
                continue
            provider_rule_seen = True
            if not _version_matches(ticket.payload, rule):
                continue
            version_accepted = True
            conditions = rule.get("conditions") or []
            if rule.get("catchAll") is True or all(
                _condition_matches(ticket.payload, condition) for condition in conditions
            ):
                candidates.append(
                    (
                        int(rule.get("priority", 0)),
                        project_id,
                        str(rule.get("id", "route")),
                        _timestamp(project.get("intakeStartedAt")),
                    )
                )
    if not candidates:
        if provider_rule_seen and not version_accepted:
            return RouteDecision("ignored_by_version", None)
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
    selected_intake = next(item[3] for item in top if item[1] == unique_projects[0])
    if (
        ticket_created_at is None
        or selected_intake is None
        or ticket_created_at < selected_intake
    ):
        return RouteDecision("ignored_before_intake", None)
    return RouteDecision("matched", unique_projects[0])
