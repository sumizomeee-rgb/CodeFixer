from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from codefixer.adapters.sources.common import CliSourceBase, SourceCommandError
from codefixer.infrastructure.process_runner import ProcessRunner


@dataclass(frozen=True)
class MaterializedTarget:
    target_branch: str
    source_branch: str
    delivery_commit: str
    target_commit: str
    merge_request_iid: str
    merge_request_url: str


def safe_branch_component(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip(".-")
    return cleaned[:80] or "target"


def _safe_relative(path: str) -> Path:
    normalized = path.replace("\\", "/")
    candidate = Path(normalized)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise SourceCommandError(f"unsafe mapped path: {path}")
    return candidate


def _map_path(path: str, mappings: tuple[tuple[str, str], ...]) -> str:
    normalized = path.replace("\\", "/").strip("/")
    matches: list[tuple[int, str]] = []
    for source, target in mappings:
        source_norm = source.replace("\\", "/").strip("/")
        target_norm = target.replace("\\", "/").strip("/")
        if source_norm in {"", "."}:
            suffix = normalized
        elif normalized == source_norm:
            suffix = ""
        elif normalized.startswith(source_norm + "/"):
            suffix = normalized[len(source_norm) + 1 :]
        else:
            continue
        mapped = "/".join(part for part in (target_norm, suffix) if part) or "."
        matches.append((len(source_norm), mapped))
    if not matches:
        raise SourceCommandError(f"no pathMapping for frozen file: {path}")
    return max(matches, key=lambda item: item[0])[1]


class GitDeliveryMaterializer(CliSourceBase):
    def __init__(self, repository: Path, command_prefix: list[str], runner: ProcessRunner | None = None, remote: str = "origin"):
        super().__init__(command_prefix, runner)
        self.repository = repository.resolve()
        self.remote = remote

    def refresh(self) -> None:
        self._run(["fetch", "--prune", self.remote], cwd=self.repository, timeout=600)

    def remote_url(self) -> str:
        value = self._run(["remote", "get-url", self.remote], cwd=self.repository).stdout.strip()
        if not value:
            raise SourceCommandError(f"Git remote has no URL: {self.remote}")
        return value

    def remote_branch_commit(self, branch: str) -> str | None:
        result = self._run(
            ["ls-remote", "--heads", self.remote, f"refs/heads/{branch}"],
            cwd=self.repository,
            allow_failure=True,
            timeout=60,
        )
        if result.exit_code != 0 or not result.stdout.strip():
            return None
        return result.stdout.split()[0]

    @staticmethod
    def _project_url(remote_url: str) -> str:
        value = remote_url.removesuffix(".git")
        scp_match = re.fullmatch(r"[^@]+@([^:]+):(.+)", value)
        if scp_match:
            return f"https://{scp_match.group(1)}/{scp_match.group(2)}"
        ssh_match = re.fullmatch(r"ssh://(?:[^@]+@)?([^/]+)/(.+)", value)
        if ssh_match:
            return f"https://{ssh_match.group(1)}/{ssh_match.group(2)}"
        return value

    def commit_exists(self, commit: str) -> bool:
        result = self._run(["cat-file", "-e", f"{commit}^{{commit}}"], cwd=self.repository, allow_failure=True)
        return result.exit_code == 0

    def create_delivery_commit(self, *, base_revision: str, patch_path: Path, worktree: Path, message: str) -> str:
        if worktree.exists():
            raise SourceCommandError(f"materialization worktree exists: {worktree}")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        self._run(["worktree", "add", "--detach", str(worktree), base_revision], cwd=self.repository)
        try:
            self._run(["apply", "--index", "--binary", str(patch_path.resolve())], cwd=worktree)
            self._run(["-c", "user.name=CodeFixer", "-c", "user.email=codefixer@local", "commit", "-m", message], cwd=worktree)
            commit = self._run(["rev-parse", "HEAD"], cwd=worktree).stdout.strip()
            if not commit:
                raise SourceCommandError("delivery commit is empty")
            return commit
        finally:
            self._run(["worktree", "remove", "--force", str(worktree)], cwd=self.repository, allow_failure=True)

    def create_mapped_delivery_commit(self, *, base_ref: str, frozen_manifest: Path, path_mappings: tuple[tuple[str, str], ...], worktree: Path, message: str) -> str:
        if not path_mappings:
            raise SourceCommandError("mapped materialization requires pathMappings")
        if worktree.exists():
            raise SourceCommandError(f"materialization worktree exists: {worktree}")
        manifest = json.loads(frozen_manifest.read_text(encoding="utf-8"))
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise SourceCommandError("frozen manifest has no files")
        worktree.parent.mkdir(parents=True, exist_ok=True)
        self._run(["worktree", "add", "--detach", str(worktree), base_ref], cwd=self.repository)
        try:
            for item in files:
                if not isinstance(item, dict):
                    raise SourceCommandError("invalid frozen file entry")
                source_path = str(item.get("path", ""))
                operation = str(item.get("operation", "modify"))
                if operation == "rename":
                    raise SourceCommandError("cross-repository pathMappings do not support rename yet")
                mapped = _safe_relative(_map_path(source_path, path_mappings))
                target = (worktree / mapped).resolve()
                try:
                    target.relative_to(worktree.resolve())
                except ValueError as exc:
                    raise SourceCommandError(f"mapped path escapes repository: {source_path}") from exc
                if operation == "delete":
                    if target.is_dir():
                        shutil.rmtree(target)
                    else:
                        target.unlink(missing_ok=True)
                    continue
                snapshot = frozen_manifest.parent / "files" / _safe_relative(source_path)
                if not snapshot.is_file():
                    raise SourceCommandError(f"frozen file snapshot missing: {source_path}")
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(snapshot, target)
            self._run(["add", "-A", "--"], cwd=worktree)
            status = self._run(["status", "--porcelain"], cwd=worktree).stdout
            if not status.strip():
                raise SourceCommandError("mapped materialization produced no Git diff")
            self._run(["-c", "user.name=CodeFixer", "-c", "user.email=codefixer@local", "commit", "-m", message], cwd=worktree)
            commit = self._run(["rev-parse", "HEAD"], cwd=worktree).stdout.strip()
            if not commit:
                raise SourceCommandError("mapped delivery commit is empty")
            return commit
        finally:
            self._run(["worktree", "remove", "--force", str(worktree)], cwd=self.repository, allow_failure=True)

    def materialize_target(self, *, delivery_commit: str, target_branch: str, source_branch: str, worktree: Path, title: str, description: str) -> MaterializedTarget:
        remote_target = f"{self.remote}/{target_branch}"
        self._run(["rev-parse", "--verify", remote_target], cwd=self.repository)
        self._run(["worktree", "add", "--detach", str(worktree), remote_target], cwd=self.repository)
        try:
            self._run(["-c", "user.name=CodeFixer", "-c", "user.email=codefixer@local", "cherry-pick", delivery_commit], cwd=worktree)
            target_commit = self._run(["rev-parse", "HEAD"], cwd=worktree).stdout.strip()
            push = self._run(
                [
                    "push",
                    self.remote,
                    f"HEAD:refs/heads/{source_branch}",
                    "-o",
                    "merge_request.create",
                    "-o",
                    f"merge_request.target={target_branch}",
                    "-o",
                    "merge_request.remove_source_branch",
                    "-o",
                    f"merge_request.title={title}",
                    "-o",
                    f"merge_request.description={description.replace(chr(10), ' ')}",
                ],
                cwd=worktree,
                timeout=600,
            )
            output = f"{push.stdout}\n{push.stderr}"
            match = re.search(r"https?://\S+/-/merge_requests/(?P<iid>\d+)", output)
            project_url = self._project_url(self.remote_url())
            merge_request_iid = match.group("iid") if match else source_branch
            merge_request_url = (
                match.group(0).rstrip(".,)")
                if match
                else f"{project_url}/-/merge_requests?scope=all&state=opened&source_branch={source_branch}"
            )
            return MaterializedTarget(
                target_branch,
                source_branch,
                delivery_commit,
                target_commit,
                merge_request_iid,
                merge_request_url,
            )
        finally:
            self._run(["worktree", "remove", "--force", str(worktree)], cwd=self.repository, allow_failure=True)
