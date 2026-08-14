from __future__ import annotations

import hashlib
from pathlib import Path

from codefixer.adapters.delivery_patch import FallbackPatchFinalAction, PatchFinalAction
from codefixer.application.ports.delivery import FinalActionResult, FrozenDeliveryContext
from codefixer.application.services.delivery import DeliveryCoordinator
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.delivery_store import DeliveryStore


class ResultAction:
    def __init__(self, action_id: str, action_type: str, result: FinalActionResult) -> None:
        self.action_id = action_id
        self.action_type = action_type
        self.result = result

    def execute(self, context: FrozenDeliveryContext) -> FinalActionResult:
        return self.result


class RaisingAction:
    action_id = "broken"
    action_type = "githubPr"

    def execute(self, context: FrozenDeliveryContext) -> FinalActionResult:
        raise RuntimeError("boom")


def _seed_run(connection: object) -> None:
    connection.execute(  # type: ignore[attr-defined]
        "INSERT INTO ticket_records(provider_instance_id,external_ticket_id,title) "
        "VALUES ('p','1','t')"
    )
    connection.execute(  # type: ignore[attr-defined]
        "INSERT INTO tasks(id,ticket_record_id,project_id,status) "
        "VALUES ('task',1,'project','running')"
    )
    connection.execute(  # type: ignore[attr-defined]
        "INSERT INTO task_runs(id,task_id,status,execution_mode_snapshot) "
        "VALUES ('run','task','running','automatic')"
    )
    connection.commit()  # type: ignore[attr-defined]


def _context(tmp_path: Path) -> FrozenDeliveryContext:
    patch_path = tmp_path / "change.patch"
    patch_path.write_bytes(b"frozen patch\n")
    manifest_path = tmp_path / "change-manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")
    metadata_path = tmp_path / "delivery-metadata.json"
    metadata_path.write_text("{}", encoding="utf-8")
    return FrozenDeliveryContext(
        task_id="task",
        run_id="run",
        change_version=2,
        source_id="source",
        base_revision="base",
        patch_path=patch_path,
        patch_sha256=hashlib.sha256(patch_path.read_bytes()).hexdigest(),
        manifest_path=manifest_path,
        delivery_metadata_path=metadata_path,
        commit_subject="fix：【Code】【#1】【v1】模块 - 修复  提交人：测试",
        patch_filename="fix-1.patch",
        ticket_key="1",
    )


def test_exception_does_not_stop_sibling_and_fallback_is_not_required_success(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    with connect_database(data_root / "db.sqlite") as connection:
        apply_migrations(connection)
        _seed_run(connection)
        store = DeliveryStore(connection)
        successful_patch = PatchFinalAction(
            action_id="normal-patch",
            action_version=1,
            store=store,
            output_directory=tmp_path / "patches",
        )
        coordinator = DeliveryCoordinator(
            (RaisingAction(), successful_patch),
            fallback_action=FallbackPatchFinalAction(
                store=store, data_root=data_root, project_id="project"
            ),
        )

        report = coordinator.execute_report(_context(tmp_path))

        assert report.outcome == "partial_success"
        assert report.succeeded is False
        assert [item.action_id for item in report.required_results] == [
            "broken",
            "normal-patch",
        ]
        assert report.required_results[1].succeeded is True
        assert report.fallback_available is True
        assert report.fallback_result is not None
        assert report.fallback_result.detail["reusedActionId"] == "normal-patch"
        assert not (data_root / "fallback-patches").exists()


def test_remote_failure_without_patch_creates_one_managed_fallback(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    remote_failure = FinalActionResult(
        "github-pr",
        "githubPr",
        "failed",
        "failure",
        {"error": "denied"},
    )
    with connect_database(data_root / "db.sqlite") as connection:
        apply_migrations(connection)
        _seed_run(connection)
        store = DeliveryStore(connection)
        coordinator = DeliveryCoordinator(
            (ResultAction("github-pr", "githubPr", remote_failure),),
            fallback_action=FallbackPatchFinalAction(
                store=store, data_root=data_root, project_id="../Unsafe 项目"
            ),
        )
        context = _context(tmp_path)

        first = coordinator.execute_report(context)
        second = coordinator.execute_report(context)

        assert first.succeeded is False
        assert first.outcome == "fallback_available"
        assert first.fallback_result is not None
        assert second.fallback_result is not None
        assert second.fallback_result.detail["adoptedExisting"] is True
        fallback_path = Path(str(first.fallback_result.detail["path"]))
        assert fallback_path.read_bytes() == context.patch_path.read_bytes()
        assert fallback_path.parent.parent.name == "fallback-patches"
        actions = connection.execute(
            "SELECT action_id, action_type, status FROM delivery_action_runs ORDER BY id"
        ).fetchall()
        assert [tuple(row) for row in actions] == [
            ("__fallback_patch__", "fallbackPatch", "succeeded")
        ]
