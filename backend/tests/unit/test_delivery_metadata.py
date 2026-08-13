from __future__ import annotations

from codefixer.application.services.delivery_metadata import build_delivery_metadata


PROJECT = {
    "deliveryLog": {
        "technologyTag": "Lua",
        "branchLabel": "主干",
        "versionSource": "ticketFixVersion",
        "versionFallback": "v4.7",
        "submitterName": "黄永熙",
    }
}
REPAIR = {"module_name": "阵容", "change_summary": "卡片匹配度修复"}


def test_tapd_bug_uses_fix_and_b_prefix() -> None:
    result = build_delivery_metadata(
        context={
            "provider_instance_id": "tapd-main",
            "external_ticket_id": "1250062",
            "ticket_payload": {"provider": "tapd", "ticketKind": "bug", "versionFix": "v4.8"},
        },
        project=PROJECT,
        repair=REPAIR,
    )

    assert result["ticket_key"] == "B1250062"
    assert result["commit_subject"] == "fix：【Lua】【#B1250062】【主干】【v4.8】阵容 - 卡片匹配度修复  提交人：黄永熙"
    assert result["patch_filename"].endswith(".patch")
    assert ":" not in result["patch_filename"]


def test_tapd_story_uses_feat_and_s_prefix() -> None:
    result = build_delivery_metadata(
        context={
            "provider_instance_id": "tapd-main",
            "external_ticket_id": "1149986",
            "ticket_payload": {"provider": "tapd", "ticketKind": "story"},
        },
        project=PROJECT,
        repair={"module_name": "音频支持", "change_summary": "音乐特效彩蛋"},
    )

    assert result["ticket_key"] == "S1149986"
    assert result["conventional_type"] == "feat"


def test_redmine_always_uses_fix_without_letter_prefix() -> None:
    result = build_delivery_metadata(
        context={
            "provider_instance_id": "redmine-main",
            "external_ticket_id": "1149986",
            "ticket_payload": {"provider": "redmine", "type": "feature", "version": {"name": "v4.7"}},
        },
        project=PROJECT,
        repair={"module_name": "音频支持", "change_summary": "音乐特效彩蛋"},
    )

    assert result["ticket_key"] == "1149986"
    assert result["commit_subject"].startswith("fix：【Lua】【#1149986】")
