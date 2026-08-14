from __future__ import annotations

import subprocess
from pathlib import Path

from codefixer.adapters.delivery.gitlab import GitDeliveryMaterializer, GitLabPushFinalAction
from codefixer.application.ports.delivery import FrozenDeliveryContext
from codefixer.infrastructure.database import apply_migrations, connect_database
from codefixer.infrastructure.delivery_store import DeliveryStore


class FakeMaterializer:
    def __init__(self) -> None:
        self.create_calls = 0
        self.push_calls = 0
        self.remote_branches: dict[str, str] = {}

    def refresh(self) -> None:
        pass

    def commit_exists(self, commit: str) -> bool:
        return commit == "delivery-commit"

    def create_delivery_commit(self, **kwargs: object) -> str:
        self.create_calls += 1
        return "delivery-commit"

    def remote_branch_commit(self, branch: str) -> str | None:
        return self.remote_branches.get(branch)

    def push_commit(self, commit: str, branch: str) -> None:
        self.push_calls += 1
        self.remote_branches[branch] = commit

    def remote_url(self) -> str:
        return "git@gitlab.example:group/project.git"


def seed_run(connection) -> None:
    connection.execute("INSERT INTO ticket_records(provider_instance_id,external_ticket_id,title) VALUES ('p','1','t')")
    connection.execute("INSERT INTO tasks(id,ticket_record_id,project_id,status) VALUES ('task',1,'project','running')")
    connection.execute("INSERT INTO task_runs(id,task_id,status,execution_mode_snapshot) VALUES ('run-1234567890abcdef','task','running','automatic')")
    connection.commit()


def context(patch: Path, *, base_revision: str = "base", run_id: str = "run-1234567890abcdef") -> FrozenDeliveryContext:
    return FrozenDeliveryContext(
        task_id="task",
        run_id=run_id,
        change_version=1,
        source_id="source",
        base_revision=base_revision,
        patch_path=patch,
        patch_sha256="a" * 64,
        manifest_path=patch.parent / "manifest.json",
        delivery_metadata_path=patch.parent / "delivery-metadata.json",
        commit_subject="fix：【Lua】【#B42】【v1】模块 - 修复问题  提交人：Tester",
        patch_filename="repair.patch",
        ticket_key="B42",
    )


def test_gitlab_push_is_idempotent_and_returns_commit_url(tmp_path: Path) -> None:
    patch = tmp_path / "change.patch"
    patch.write_text("diff\n", encoding="utf-8")
    with connect_database(tmp_path / "db.sqlite") as connection:
        apply_migrations(connection)
        seed_run(connection)
        materializer = FakeMaterializer()
        action = GitLabPushFinalAction(
            action_id="gitlab-push",
            action_version=1,
            store=DeliveryStore(connection),
            materializer=materializer,
            config={"id": "gitlab-push", "type": "gitlabPush"},
            work_root=tmp_path / "work",
            web_base_url="https://gitlab.example",
        )

        first = action.execute(context(patch))
        second = action.execute(context(patch))

        assert first.succeeded is True
        assert first.detail["commitUrl"] == "https://gitlab.example/group/project/-/commit/delivery-commit"
        assert first.detail["remoteBranch"] == "codefixer/B42/run-12345678"
        assert second.detail["adoptedExisting"] is True
        assert materializer.create_calls == 1
        assert materializer.push_calls == 1


def git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip()


class LocalRemoteMaterializer(GitDeliveryMaterializer):
    def remote_url(self) -> str:
        return "git@gitlab.example:group/project.git"


def test_gitlab_push_executes_real_git_commit_and_remote_push(tmp_path: Path) -> None:
    remote = tmp_path / "remote.git"
    repository = tmp_path / "repository"
    remote.mkdir()
    repository.mkdir()
    git(remote, "init", "--bare", "-q")
    git(repository, "init", "-q")
    git(repository, "config", "user.name", "Fixture")
    git(repository, "config", "user.email", "fixture@example.test")
    git(repository, "config", "core.autocrlf", "false")
    source = repository / "app.txt"
    source.write_text("old\n", encoding="utf-8")
    git(repository, "add", "app.txt")
    git(repository, "commit", "-q", "-m", "base")
    base_revision = git(repository, "rev-parse", "HEAD")
    git(repository, "remote", "add", "origin", str(remote))
    git(repository, "push", "-q", "origin", "HEAD:refs/heads/main")
    source.write_text("new\n", encoding="utf-8")
    patch = tmp_path / "change.patch"
    patch.write_text(git(repository, "diff", "--binary") + "\n", encoding="utf-8")
    git(repository, "restore", "app.txt")

    with connect_database(tmp_path / "real-db.sqlite") as connection:
        apply_migrations(connection)
        seed_run(connection)
        action = GitLabPushFinalAction(
            action_id="gitlab-push-real",
            action_version=1,
            store=DeliveryStore(connection),
            materializer=LocalRemoteMaterializer(repository, ["git"]),
            config={"id": "gitlab-push-real", "type": "gitlabPush"},
            work_root=tmp_path / "work-real",
            web_base_url="https://gitlab.example",
        )

        result = action.execute(context(patch, base_revision=base_revision))

    assert result.succeeded is True
    remote_branch = str(result.detail["remoteBranch"])
    remote_sha = git(remote, "rev-parse", f"refs/heads/{remote_branch}")
    assert remote_sha == result.detail["commitSha"]
    assert git(repository, "show", "-s", "--format=%s", remote_sha) == context(patch).commit_subject
