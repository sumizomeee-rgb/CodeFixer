from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

import httpx


class GitLabApiError(RuntimeError):
    pass


@dataclass(frozen=True)
class MergeRequestRef:
    iid: str
    web_url: str
    state: str
    source_branch: str
    target_branch: str


class GitLabClient:
    def __init__(self, base_url: str, token: str, client: httpx.Client | None = None):
        if not token:
            raise ValueError("GitLab token is required")
        self.base_url = base_url.rstrip("/")
        self.client = client or httpx.Client(base_url=f"{self.base_url}/api/v4", headers={"PRIVATE-TOKEN": token, "Accept": "application/json"}, timeout=30.0)

    @staticmethod
    def _project(project_id: str | int) -> str:
        return quote(str(project_id), safe="")

    def find_merge_request(self, project_id: str | int, source_branch: str, target_branch: str) -> MergeRequestRef | None:
        response = self.client.get(f"/projects/{self._project(project_id)}/merge_requests", params={"scope": "all", "state": "all", "source_branch": source_branch, "target_branch": target_branch, "per_page": 20})
        response.raise_for_status()
        values = response.json()
        if not isinstance(values, list):
            raise GitLabApiError("GitLab merge request list must be an array")
        exact = [item for item in values if isinstance(item, dict) and item.get("source_branch") == source_branch and item.get("target_branch") == target_branch]
        if not exact:
            return None
        if len(exact) > 1:
            raise GitLabApiError("multiple merge requests match the same delivery branch pair")
        item = exact[0]
        return MergeRequestRef(iid=str(item.get("iid", "")), web_url=str(item.get("web_url", "")), state=str(item.get("state", "")), source_branch=source_branch, target_branch=target_branch)

    def get_branch_commit(self, project_id: str | int, branch: str) -> str | None:
        response = self.client.get(f"/projects/{self._project(project_id)}/repository/branches/{quote(branch, safe='')}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise GitLabApiError("GitLab branch response must be an object")
        commit = payload.get("commit")
        if not isinstance(commit, dict) or not commit.get("id"):
            raise GitLabApiError("GitLab branch response has no commit")
        return str(commit["id"])

    def create_merge_request(self, project_id: str | int, *, source_branch: str, target_branch: str, title: str, description: str) -> MergeRequestRef:
        response = self.client.post(f"/projects/{self._project(project_id)}/merge_requests", data={"source_branch": source_branch, "target_branch": target_branch, "title": title, "description": description})
        response.raise_for_status()
        item = response.json()
        if not isinstance(item, dict):
            raise GitLabApiError("GitLab create merge request response must be an object")
        return MergeRequestRef(iid=str(item.get("iid", "")), web_url=str(item.get("web_url", "")), state=str(item.get("state", "opened")), source_branch=source_branch, target_branch=target_branch)
