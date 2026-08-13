from __future__ import annotations

from pathlib import Path

from codefixer.adapters.delivery.gitlab import GitLabMrDelivery
from codefixer.adapters.sources.common import SourceCommandError
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.delivery_store import DeliveryStore


class FakeMaterializer:
    def __init__(self):
        self.materialize_calls = 0
        self.remote_branches: dict[str, str] = {}

    def refresh(self):
        pass

    def commit_exists(self, commit):
        return commit == "delivery-commit"

    def create_delivery_commit(self, **kwargs):
        return "delivery-commit"

    def remote_branch_commit(self, branch):
        return self.remote_branches.get(branch)

    def materialize_target(self, **kwargs):
        self.materialize_calls += 1
        source_branch = kwargs["source_branch"]
        self.remote_branches[source_branch] = "target-commit"

        class Result:
            target_commit = "target-commit"
            merge_request_iid = "42"
            merge_request_url = "https://gitlab.example/group/project/-/merge_requests/42"

        return Result()


def seed_run(connection):
    connection.execute("INSERT INTO ticket_records(provider_instance_id,external_ticket_id,title) VALUES ('p','1','t')")
    connection.execute("INSERT INTO tasks(id,ticket_record_id,project_id,status) VALUES ('task',1,'project','running')")
    connection.execute("INSERT INTO task_runs(id,task_id,status,execution_mode_snapshot) VALUES ('run','task','running','automatic')")
    connection.commit()


def deliver(delivery, patch: Path, work_root: Path, targets=("main",)):
    return delivery.deliver(
        task_id="task",
        run_id="run",
        action_id="mr",
        action_version=1,
        config={"repositoryRef": "repo", "targetBranches": list(targets)},
        frozen_patch=patch,
        base_revision="base",
        target_branches=targets,
        work_root=work_root,
        title="Fix",
        description="d",
    )


def test_restart_reuses_persisted_success_without_duplicate_push(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    patch = tmp_path / "change.patch"
    patch.write_text("diff\n")
    with connect_database(data / "db.sqlite") as connection:
        apply_migrations(connection)
        seed_run(connection)
        store = DeliveryStore(connection)
        materializer = FakeMaterializer()
        delivery = GitLabMrDelivery(store, materializer)
        first = deliver(delivery, patch, tmp_path / "work")
        second = deliver(delivery, patch, tmp_path / "work2")
        assert first[0].merge_request.iid == "42"
        assert second[0].adopted_existing is True
        assert materializer.materialize_calls == 1


class PartialMaterializer(FakeMaterializer):
    def materialize_target(self, **kwargs):
        if kwargs["target_branch"] == "release/bad":
            raise SourceCommandError("cherry-pick conflict")
        return super().materialize_target(**kwargs)


def test_one_target_conflict_does_not_hide_other_target_success(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    patch = tmp_path / "change.patch"
    patch.write_text("diff\n")
    with connect_database(data / "db.sqlite") as connection:
        apply_migrations(connection)
        seed_run(connection)
        store = DeliveryStore(connection)
        delivery = GitLabMrDelivery(store, PartialMaterializer())
        results = deliver(delivery, patch, tmp_path / "work", ("release/bad", "main"))
        assert [item.target_branch for item in results] == ["main"]
        action = store.get_action(1)
        assert action["status"] == "failed"
        assert action["outcome"] == "partial_success"
