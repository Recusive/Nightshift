"""Git worktree lifecycle: create, shift log, sync, revert, cleanup."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from nightshift.config import infer_install_command
from nightshift.constants import (
    SAFE_ARTIFACT_DIRS,
    SAFE_ARTIFACT_GLOBS,
    SHIFT_LOG_TEMPLATE,
    now_local,
    print_status,
)
from nightshift.errors import NightshiftError
from nightshift.shell import git, run_command


def _missing_gitdir_hint(worktree_dir: Path) -> str | None:
    git_file = worktree_dir / ".git"
    if not git_file.is_file():
        return None
    content = git_file.read_text(encoding="utf-8").strip()
    if not content.startswith("gitdir:"):
        return None
    gitdir = Path(content.split(":", 1)[1].strip())
    if gitdir.exists():
        return None
    return f"Worktree .git points to missing gitdir `{gitdir}`."


def validate_worktree(worktree_dir: Path) -> None:
    try:
        inside = git(worktree_dir, "rev-parse", "--is-inside-work-tree")
    except NightshiftError as error:
        hint = _missing_gitdir_hint(worktree_dir)
        if hint is not None:
            raise NightshiftError(f"Broken git worktree at {worktree_dir}. {hint}") from error
        raise NightshiftError(f"Broken git worktree at {worktree_dir}: {error}") from error
    if inside.strip() != "true":
        raise NightshiftError(f"Broken git worktree at {worktree_dir}: git did not confirm a worktree.")


def validate_repo_checkout(repo_dir: Path) -> None:
    try:
        inside = git(repo_dir, "rev-parse", "--is-inside-work-tree")
    except NightshiftError as error:
        raise NightshiftError(f"Target repo is not a valid git checkout: {repo_dir}") from error
    if inside.strip() != "true":
        raise NightshiftError(f"Target repo is not a valid git checkout: {repo_dir}")


def ensure_worktree(repo_dir: Path, worktree_dir: Path, branch: str) -> None:
    validate_repo_checkout(repo_dir)
    git(repo_dir, "worktree", "prune", check=False)
    if worktree_dir.exists():
        print_status(f"Resuming existing worktree at: {worktree_dir}")
        try:
            validate_worktree(worktree_dir)
            return
        except NightshiftError as error:
            print_status(f"{error} Recreating worktree.")
            shutil.rmtree(worktree_dir, ignore_errors=True)
            git(repo_dir, "worktree", "prune", check=False)
    print_status(f"Creating worktree at: {worktree_dir}")
    branch_exists = bool(git(repo_dir, "branch", "--list", branch))
    try:
        if branch_exists:
            git(repo_dir, "worktree", "add", str(worktree_dir), branch)
        else:
            git(repo_dir, "worktree", "add", str(worktree_dir), "-b", branch)
    except NightshiftError as error:
        if "already registered worktree" not in str(error):
            raise
        git(repo_dir, "worktree", "prune", check=False)
        if branch_exists:
            git(repo_dir, "worktree", "add", "-f", str(worktree_dir), branch)
        else:
            git(repo_dir, "worktree", "add", "-f", str(worktree_dir), "-b", branch)
    validate_worktree(worktree_dir)


def ensure_shift_log(shift_log_path: Path, *, today: str, branch: str, base_branch: str) -> None:
    if shift_log_path.exists():
        return
    shift_log_path.parent.mkdir(parents=True, exist_ok=True)
    shift_log_path.write_text(
        SHIFT_LOG_TEMPLATE.format(
            today=today,
            branch=branch,
            base_branch=base_branch,
            started=now_local().strftime("%H:%M"),
        ),
        encoding="utf-8",
    )


def ensure_shift_log_committed(worktree_dir: Path, shift_log_relative: str) -> None:
    tracked = (
        subprocess.run(
            ["git", "ls-files", "--error-unmatch", shift_log_relative],
            cwd=str(worktree_dir),
            text=True,
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )
    if tracked:
        return
    status = git(worktree_dir, "status", "--porcelain", check=False)
    if shift_log_relative not in status:
        return
    git(worktree_dir, "add", shift_log_relative)
    git(
        worktree_dir,
        "commit",
        "-m",
        "nightshift: [meta] initialize shift log\n\nWhat: add the initial overnight shift scaffold\nFix: create the shift log before cycle work begins",
    )


def discover_base_branch(repo_dir: Path) -> str:
    try:
        origin_head = git(repo_dir, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
        return origin_head.rsplit("/", 1)[-1]
    except NightshiftError:
        return git(repo_dir, "branch", "--show-current")


def install_dependencies_if_needed(worktree_dir: Path, runner_log: Path) -> None:
    install_cmd = infer_install_command(worktree_dir)
    if not install_cmd:
        return
    marker = worktree_dir / "node_modules"
    if marker.exists():
        return
    print_status("Installing dependencies in worktree...")
    exit_code, _ = run_command(install_cmd, cwd=worktree_dir, log_path=runner_log)
    if exit_code != 0:
        raise NightshiftError("Dependency install failed in worktree")


def sync_shift_log(worktree_dir: Path, repo_dir: Path, shift_log_relative: str) -> None:
    source = worktree_dir / shift_log_relative
    if not source.exists():
        return
    target = repo_dir / shift_log_relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def git_changed_files_for_commit(worktree_dir: Path, commit: str) -> list[str]:
    output = git(worktree_dir, "show", "--pretty=format:", "--name-only", commit)
    return [line.strip() for line in output.splitlines() if line.strip()]


def git_name_status_for_commit(worktree_dir: Path, commit: str) -> list[str]:
    output = git(worktree_dir, "show", "--pretty=format:", "--name-status", commit)
    return [line.strip() for line in output.splitlines() if line.strip()]


def revert_cycle(worktree_dir: Path, pre_head: str) -> None:
    subprocess.run(["git", "reset", "--hard", pre_head], cwd=str(worktree_dir), check=False)
    subprocess.run(["git", "clean", "-fd"], cwd=str(worktree_dir), check=False)


def cleanup_safe_artifacts(worktree_dir: Path) -> None:
    for directory_name in SAFE_ARTIFACT_DIRS:
        for path in worktree_dir.rglob(directory_name):
            if path.is_dir():
                subprocess.run(["rm", "-rf", str(path)], check=False)
    for pattern in SAFE_ARTIFACT_GLOBS:
        for path in worktree_dir.rglob(pattern):
            if path.is_file():
                path.unlink(missing_ok=True)
