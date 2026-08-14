from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path


class GitRepositoryCacheError(RuntimeError):
    """Git 仓库缓存无法创建或校验。"""


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return

    def remove_readonly(function: object, raw_path: str, _: object) -> None:
        os.chmod(raw_path, stat.S_IREAD | stat.S_IWRITE)
        function(raw_path)  # type: ignore[operator]

    try:
        shutil.rmtree(path, onerror=remove_readonly)
    except OSError:
        raise GitRepositoryCacheError("Git 缓存临时目录清理失败") from None


def _run_git(
    command: list[str],
    *,
    cwd: Path,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except (OSError, subprocess.TimeoutExpired):
        # TimeoutExpired 包含完整命令，不能将可能含凭据的 URL 挂到异常链上。
        raise GitRepositoryCacheError("Git 缓存命令无法执行") from None


def _validate_repository(
    repository: Path,
    *,
    remote_url: str,
    command_prefix: list[str],
) -> None:
    if not repository.is_dir():
        raise GitRepositoryCacheError("Git 缓存目录结构无效")

    work_tree = _run_git(
        [*command_prefix, "rev-parse", "--is-inside-work-tree"],
        cwd=repository,
        timeout_seconds=30,
    )
    bare = _run_git(
        [*command_prefix, "rev-parse", "--is-bare-repository"],
        cwd=repository,
        timeout_seconds=30,
    )
    if (
        work_tree.returncode != 0
        or work_tree.stdout.strip() != "true"
        or bare.returncode != 0
        or bare.stdout.strip() != "false"
    ):
        raise GitRepositoryCacheError("Git 缓存目录结构无效")

    origin = _run_git(
        [*command_prefix, "remote", "get-url", "origin"],
        cwd=repository,
        timeout_seconds=30,
    )
    if origin.returncode != 0 or origin.stdout.strip() != remote_url:
        raise GitRepositoryCacheError("Git 缓存 origin 与请求来源不一致")


def ensure_git_repository(
    remote_url: str,
    cache_root: Path,
    command_prefix: list[str],
) -> Path:
    """确保远程 Git 仓库有一个可共享 worktree 的本地缓存。

    已存在的缓存只校验结构和 origin，远程更新由运行期适配器严格执行。
    """

    normalized_url = remote_url.strip()
    if not normalized_url:
        raise GitRepositoryCacheError("Git 远程地址不能为空")
    if not command_prefix:
        raise GitRepositoryCacheError("Git 命令前缀不能为空")

    root = cache_root.resolve(strict=False)
    root.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
    repository = root / cache_key
    if repository.exists() or repository.is_symlink():
        _validate_repository(
            repository,
            remote_url=normalized_url,
            command_prefix=command_prefix,
        )
        return repository

    # 暂存目录不重复长哈希，避免 Windows 下 Git 内部引用路径超限。
    staging_root = Path(tempfile.mkdtemp(prefix=".tmp-", dir=root))
    candidate = staging_root / "repository"
    try:
        clone = _run_git(
            [
                *command_prefix,
                "clone",
                "--no-checkout",
                "--origin",
                "origin",
                "--",
                normalized_url,
                str(candidate),
            ],
            cwd=root,
            timeout_seconds=600,
        )
        if clone.returncode != 0:
            raise GitRepositoryCacheError("Git 远程缓存初始化失败")
        _validate_repository(
            candidate,
            remote_url=normalized_url,
            command_prefix=command_prefix,
        )
        try:
            candidate.rename(repository)
        except OSError:
            # 另一进程可能已经完成同一仓库的原子发布。
            if not (repository.exists() or repository.is_symlink()):
                raise GitRepositoryCacheError("Git 远程缓存发布失败") from None
        _validate_repository(
            repository,
            remote_url=normalized_url,
            command_prefix=command_prefix,
        )
        return repository
    finally:
        _remove_tree(staging_root)
