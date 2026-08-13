from __future__ import annotations

from pathlib import Path

from codefixer.adapters.delivery.github import GitHubPrDelivery, PullRequestRef
from codefixer.adapters.sources.common import SourceCommandError
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.delivery_store import DeliveryStore


class FakeMaterializer:
    remote = "origin"

    def __init__(self) -> None:
        self.delivery_calls = 0
        self.push_calls = 0
        self.remote_branches: dict[str, str] = {}
        self.commits = {"delivery-commit"}

    def refresh(self) -> None:
        pass

    def commit_exists(self, commit: str) -> bool:
        return commit in self.commits

    def create_delivery_commit(self, **kwargs: object) -> str:
        self.delivery_calls += 1
        return "delivery-commit"

    def create_mapped_delivery_commit(self, **kwargs: object) -> str:
        return self.create_delivery_commit(**kwargs)

    def create_target_commit(
        self, *, delivery_commit: str, target_branch: str, worktree: Path
    ) -> str:
        commit = f"commit-{target_branch}"
        self.commits.add(commit)
        return commit

    def remote_branch_commit(self, branch: str) -> str | None:
        return self.remote_branches.get(branch)

    def push_target(self, *, target_commit: str, source_branch: str) -> None:
        self.push_calls += 1
        self.remote_branches[source_branch] = target_commit


class FakeGitHub:
    def __init__(self) -> None:
        self.create_calls = 0
        self.pull_requests: dict[tuple[str, str], PullRequestRef] = {}
        self.raise_after_create_once = False

    def list_pull_requests(
        self, *, source_branch: str, target_branch: str
    ) -> tuple[PullRequestRef, ...]:
        item = self.pull_requests.get((source_branch, target_branch))
        return (item,) if item is not None else ()

    def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> PullRequestRef:
        self.create_calls += 1
        item = PullRequestRef(
            str(self.create_calls),
            f"https://github.example/org/repo/pull/{self.create_calls}",
            "open",
            source_branch,
            target_branch,
        )
        self.pull_requests[(source_branch, target_branch)] = item
        if self.raise_after_create_once:
            self.raise_after_create_once = False
            raise SourceCommandError("connection lost after create")
        return item


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


def _deliver(
    delivery: GitHubPrDelivery, patch: Path, work_root: Path, targets: tuple[str, ...]
):
    return delivery.deliver(
        task_id="task",
        run_id="run",
        action_id="pr",
        action_version=1,
        config={"targetBranches": list(targets)},
        frozen_patch=patch,
        base_revision="base",
        target_branches=targets,
        work_root=work_root,
        title="Fix",
        description="Description",
    )


def test_github_delivery_reuses_persisted_pr_without_duplicate_push(tmp_path: Path) -> None:
    patch = tmp_path / "change.patch"
    patch.write_text("diff\n", encoding="utf-8")
    with connect_database(tmp_path / "db.sqlite") as connection:
        apply_migrations(connection)
        _seed_run(connection)
        materializer = FakeMaterializer()
        github = FakeGitHub()
        delivery = GitHubPrDelivery(DeliveryStore(connection), materializer, github)

        first = _deliver(delivery, patch, tmp_path / "work", ("main", "release/1"))
        second = _deliver(delivery, patch, tmp_path / "work2", ("main", "release/1"))

        assert first.status == "succeeded"
        assert len(first.targets) == 2
        assert all(item.adopted_existing is False for item in first.targets)
        assert all(item.adopted_existing is True for item in second.targets)
        assert materializer.delivery_calls == 1
        assert materializer.push_calls == 2
        assert github.create_calls == 2


def test_retry_adopts_pr_created_before_cli_result_was_recorded(tmp_path: Path) -> None:
    patch = tmp_path / "change.patch"
    patch.write_text("diff\n", encoding="utf-8")
    with connect_database(tmp_path / "db.sqlite") as connection:
        apply_migrations(connection)
        _seed_run(connection)
        materializer = FakeMaterializer()
        github = FakeGitHub()
        github.raise_after_create_once = True
        store = DeliveryStore(connection)
        delivery = GitHubPrDelivery(store, materializer, github)

        failed = _deliver(delivery, patch, tmp_path / "work", ("main",))
        recovered = _deliver(delivery, patch, tmp_path / "work2", ("main",))

        assert failed.status == "failed"
        assert failed.outcome == "failure"
        assert recovered.status == "succeeded"
        assert recovered.targets[0].adopted_existing is True
        assert materializer.push_calls == 1
        assert github.create_calls == 1
        action = store.get_action(1)
        assert action["status"] == "succeeded"
        assert action["targets"][0]["external_url"].endswith("/pull/1")
