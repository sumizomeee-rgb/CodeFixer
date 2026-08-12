from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, Protocol

SourceType = Literal["git", "svn"]


@dataclass(frozen=True)
class SourcePolicy:
    allowed_roots: tuple[str, ...] = ()
    denied_roots: tuple[str, ...] = ()
    allowed_extensions: tuple[str, ...] = ()

    def authorize(self, relative_path: str) -> bool:
        normalized = relative_path.replace("\\", "/")
        path = PurePosixPath(normalized)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            return False
        candidate = str(path)
        if self.denied_roots and any(_within(candidate, root) for root in self.denied_roots):
            return False
        if self.allowed_roots and not any(_within(candidate, root) for root in self.allowed_roots):
            return False
        if self.allowed_extensions and path.suffix.lower() not in {item.lower() for item in self.allowed_extensions}:
            return False
        return True


@dataclass(frozen=True)
class WorkspaceManifest:
    source_type: SourceType
    source_id: str
    repository_path: Path
    workspace_path: Path
    base_revision: str
    lease_key: str | None = None
    lease_owner: str | None = None


@dataclass(frozen=True)
class CandidateChange:
    base_revision: str
    patch_text: str
    patch_sha256: str
    changed_paths: tuple[str, ...]
    unauthorized_paths: tuple[str, ...]
    operations: tuple[tuple[str, str], ...] = ()

    @property
    def valid(self) -> bool:
        return bool(self.changed_paths) and not self.unauthorized_paths


class ModificationSourceAdapter(Protocol):
    source_type: SourceType

    def current_revision(self) -> str: ...
    def prepare(self, *, source_id: str, run_id: str, workspace_path: Path, base_revision: str | None = None) -> WorkspaceManifest: ...
    def collect_change(self, manifest: WorkspaceManifest, policy: SourcePolicy) -> CandidateChange: ...
    def restore_candidate(self, manifest: WorkspaceManifest, candidate: CandidateChange) -> None: ...
    def cleanup(self, manifest: WorkspaceManifest) -> None: ...


def _within(path: str, root: str) -> bool:
    normalized = root.replace("\\", "/").strip("/")
    if normalized in {"", ".", "*"}:
        return True
    return path == normalized or path.startswith(f"{normalized}/")
