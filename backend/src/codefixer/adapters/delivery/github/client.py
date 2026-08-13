from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from codefixer.adapters.sources.common import CliSourceBase, SourceCommandError
from codefixer.infrastructure.process_runner import ProcessRunner


@dataclass(frozen=True)
class PullRequestRef:
    number: str
    web_url: str
    state: str
    source_branch: str
    target_branch: str


class GitHubCli(CliSourceBase):
    """在修改仓库目录内复用部署用户现有的 gh 认证。"""

    def __init__(
        self,
        repository: Path,
        command_prefix: list[str] | None = None,
        runner: ProcessRunner | None = None,
    ) -> None:
        super().__init__(command_prefix or ["gh"], runner)
        self.repository = repository.resolve()

    def list_pull_requests(
        self, *, source_branch: str, target_branch: str
    ) -> tuple[PullRequestRef, ...]:
        result = self._run(
            [
                "pr",
                "list",
                "--state",
                "all",
                "--head",
                source_branch,
                "--base",
                target_branch,
                "--limit",
                "100",
                "--json",
                "number,url,state,headRefName,baseRefName",
            ],
            cwd=self.repository,
            env={"GH_PROMPT_DISABLED": "1"},
            timeout=120,
        )
        try:
            payload = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise SourceCommandError("gh pr list returned invalid JSON") from exc
        if not isinstance(payload, list):
            raise SourceCommandError("gh pr list returned a non-array result")
        matches: list[PullRequestRef] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            head = str(item.get("headRefName", ""))
            base = str(item.get("baseRefName", ""))
            if head != source_branch or base != target_branch:
                continue
            matches.append(
                PullRequestRef(
                    number=str(item.get("number", "")),
                    web_url=str(item.get("url", "")),
                    state=str(item.get("state", "")).lower(),
                    source_branch=head,
                    target_branch=base,
                )
            )
        return tuple(matches)

    def create_pull_request(
        self,
        *,
        source_branch: str,
        target_branch: str,
        title: str,
        description: str,
    ) -> PullRequestRef:
        result = self._run(
            [
                "pr",
                "create",
                "--head",
                source_branch,
                "--base",
                target_branch,
                "--title",
                title,
                "--body",
                description,
            ],
            cwd=self.repository,
            env={"GH_PROMPT_DISABLED": "1"},
            timeout=180,
        )
        match = re.search(r"https?://[^\s]+/pull/(?P<number>\d+)", result.stdout)
        if match is None:
            raise SourceCommandError("gh pr create did not return a pull request URL")
        return PullRequestRef(
            number=match.group("number"),
            web_url=match.group(0).rstrip(".,)"),
            state="open",
            source_branch=source_branch,
            target_branch=target_branch,
        )
