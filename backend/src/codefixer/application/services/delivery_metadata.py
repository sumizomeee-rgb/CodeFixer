from __future__ import annotations

import hashlib
import re
from typing import Any


def _clean_text(value: object, *, fallback: str, maximum: int) -> str:
    cleaned = re.sub(r"[\r\n\t]+", " ", str(value or "")).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return (cleaned or fallback)[:maximum]


def _ticket_identity(context: dict[str, Any]) -> tuple[str, str]:
    payload = context.get("ticket_payload") if isinstance(context.get("ticket_payload"), dict) else {}
    provider = str(payload.get("provider") or context.get("provider_instance_id") or "").lower()
    raw_id = re.sub(r"^[#BSbs]+", "", str(context.get("external_ticket_id") or "").strip())
    if provider == "redmine":
        return "fix", raw_id
    kind = str(payload.get("ticketKind") or payload.get("entryType") or payload.get("type") or "bug").lower()
    is_bug = kind in {"bug", "defect", "缺陷"}
    return ("fix", f"B{raw_id}") if is_bug else ("feat", f"S{raw_id}")


def _version_label(context: dict[str, Any], config: dict[str, Any]) -> str:
    source = str(config.get("versionSource") or "fixed")
    fallback = _clean_text(config.get("versionFallback"), fallback="未标注", maximum=40)
    if source != "ticketFixVersion":
        return fallback
    payload = context.get("ticket_payload") if isinstance(context.get("ticket_payload"), dict) else {}
    value: object = payload.get("versionFix")
    if value is None:
        value = payload.get("version")
    if isinstance(value, dict):
        value = value.get("name")
    return _clean_text(value, fallback=fallback, maximum=40)


def _safe_patch_filename(subject: str) -> str:
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "-", subject).rstrip(" .")
    filename = f"{safe}.patch"
    if len(filename) <= 220:
        return filename
    suffix = hashlib.sha256(subject.encode("utf-8")).hexdigest()[:10]
    return f"{safe[:202].rstrip()}-{suffix}.patch"


def build_delivery_metadata(
    *, context: dict[str, Any], project: dict[str, Any], repair: dict[str, Any]
) -> dict[str, Any]:
    config = project.get("deliveryLog") if isinstance(project.get("deliveryLog"), dict) else {}
    conventional_type, ticket_key = _ticket_identity(context)
    technology = _clean_text(config.get("technologyTag"), fallback="Code", maximum=40)
    branch = _clean_text(config.get("branchLabel"), fallback="默认", maximum=40)
    version = _version_label(context, config)
    module = _clean_text(repair.get("module_name"), fallback="通用模块", maximum=40)
    change = _clean_text(repair.get("change_summary") or repair.get("summary"), fallback="问题修复", maximum=80)
    submitter = _clean_text(config.get("submitterName"), fallback="CodeFixer", maximum=60)
    subject = (
        f"{conventional_type}：【{technology}】【#{ticket_key}】【{branch}】【{version}】"
        f"{module} - {change}  提交人：{submitter}"
    )
    return {
        "schema_version": 1,
        "conventional_type": conventional_type,
        "technology_tag": technology,
        "ticket_key": ticket_key,
        "branch_label": branch,
        "version_label": version,
        "module_name": module,
        "change_summary": change,
        "submitter_name": submitter,
        "commit_subject": subject,
        "patch_filename": _safe_patch_filename(subject),
    }
