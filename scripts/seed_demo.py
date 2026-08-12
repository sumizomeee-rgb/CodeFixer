#!/usr/bin/env python3
"""Seed deterministic UI data into a disposable CodeFixer database.

This script is for local visual verification only. Production never calls it.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "src"))

from codefixer.config import load_config  # noqa: E402
from codefixer.domain.tasks import IngestedTicket  # noqa: E402
from codefixer.infrastructure.database import connect_database, initialize_database  # noqa: E402
from codefixer.infrastructure.task_store import TaskStore  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    loaded = load_config(ROOT / "config" / "defaults" / "codefixer.json")
    db_path = loaded.data_root / "codefixer.db"
    if args.reset and db_path.exists():
        db_path.unlink()
    db_path = initialize_database(loaded.data_root)
    with connect_database(db_path) as connection:
        count = int(connection.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()["c"])
        if count:
            print(f"demo seed skipped: {count} tasks already exist")
            return 0
        store = TaskStore(connection)
        running = store.ingest(IngestedTicket("tapd-demo", "124902", "【4.7】【商城】购买礼包后偶现红点未刷新", {"description": "UI demo"}, "v1", True), "product-lua", "automatic")
        running_run = running["runs"][0]["id"]
        store.claim_run(running_run)
        for stage, status in (("prepare", "completed"), ("discovery", "completed"), ("repair", "running")):
            sid = store.start_stage(running_run, stage, 1)
            if status != "running":
                store.finish_stage(sid, status=status)

        nochange = store.ingest(IngestedTicket("redmine-demo", "98142", "切换角色后音频遮挡参数未恢复", {"description": "UI demo"}, "v1", True), "audio-runtime", "automatic")
        nr = nochange["runs"][0]["id"]
        store.claim_run(nr)
        for stage in ("prepare", "discovery", "no_change_verify", "review", "pre_delivery_check"):
            sid = store.start_stage(nr, stage, 1)
            store.finish_stage(sid, status="completed")
        store.complete_run(nr, "no_change")

        failed = store.ingest(IngestedTicket("tapd-demo", "125081", "release/4.7 cherry-pick 冲突", {"description": "UI demo"}, "v1", True), "product-lua", "automatic")
        fr = failed["runs"][0]["id"]
        store.claim_run(fr)
        sid = store.start_stage(fr, "deliver", 1)
        store.finish_stage(sid, status="failed", failure={"code": "delivery_failed", "summary": "2 / 3 targets succeeded; release/4.7 conflicted"})
        store.fail_run(fr, {"code": "delivery_failed", "stage": "deliver", "summary": "2 / 3 个目标分支已成功，release/4.7 需要处理冲突", "retryable": True, "side_effects": ["MR !4812", "MR !4813"]})
    print(f"seeded demo database: {db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
