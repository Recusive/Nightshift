"""Auto-release version tagging -- checks readiness and creates GitHub releases."""

from __future__ import annotations

import re
from pathlib import Path

from nightshift.core.constants import (
    RELEASE_SAFE_TAG_RE,
    RELEASE_STATUS_RE,
    RELEASE_STATUS_RELEASED,
    RELEASE_TAG_RE,
    RELEASE_TASK_FRONTMATTER_RE,
    RELEASE_TASK_FRONTMATTER_STATUS_RE,
    RELEASE_TASK_TARGET_RE,
    RELEASE_VERSION_RE,
)
from nightshift.core.errors import NightshiftError
from nightshift.core.shell import git, run_capture
from nightshift.core.types import ReleaseResult


def _changelog_dir(repo_dir: Path) -> Path:
    """Return the canonical path to the .recursive/changelog/ directory."""
    return repo_dir / ".recursive" / "changelog"


def _tasks_dir(repo_dir: Path) -> Path:
    """Return the canonical path to the .recursive/tasks/ directory."""
    return repo_dir / ".recursive" / "tasks"


def _list_versions(changelog_dir: Path) -> list[str]:
    """Return sorted version strings found in the changelog directory."""
    versions = []
    for path in changelog_dir.iterdir():
        m = RELEASE_VERSION_RE.match(path.name)
        if m:
            versions.append(m.group(1))
    versions.sort(key=_parse_version_tuple)
    return versions


def _read_changelog(changelog_dir: Path, version: str) -> str:
    """Read and return the raw changelog content for *version*.

    Raises NightshiftError when the changelog file does not exist.
    """
    path = changelog_dir / f"{version}.md"
    if not path.exists():
        raise NightshiftError(f"Changelog not found for {version}: {path}")
    return path.read_text(encoding="utf-8")


def _is_already_released(changelog_content: str) -> bool:
    """Return True if the changelog header shows Status: Released."""
    m = RELEASE_STATUS_RE.search(changelog_content)
    if not m:
        return False
    return m.group(1).strip() == RELEASE_STATUS_RELEASED


def _extract_tag(changelog_content: str, version: str) -> str:
    """Return the git tag from the changelog header, falling back to *version*."""
    m = RELEASE_TAG_RE.search(changelog_content)
    if m:
        return m.group(1).strip()
    return version


def _tasks_for_version(tasks_dir: Path, version: str) -> list[Path]:
    """Return task files whose frontmatter targets *version*."""
    matched: list[Path] = []
    if not tasks_dir.exists():
        return matched
    for path in tasks_dir.glob("[0-9]*.md"):
        text = path.read_text(encoding="utf-8")
        fm_match = RELEASE_TASK_FRONTMATTER_RE.match(text)
        if not fm_match:
            continue
        frontmatter = fm_match.group(1)
        target_match = RELEASE_TASK_TARGET_RE.search(frontmatter)
        if target_match and target_match.group(1).strip() == version:
            matched.append(path)
    return matched


def _all_tasks_done(task_files: list[Path]) -> tuple[bool, list[str]]:
    """Return (all_done, list_of_pending_task_ids).

    A task is pending when its frontmatter status is anything other than "done".
    """
    pending = []
    for path in task_files:
        text = path.read_text(encoding="utf-8")
        fm_match = RELEASE_TASK_FRONTMATTER_RE.match(text)
        if not fm_match:
            pending.append(path.stem)
            continue
        frontmatter = fm_match.group(1)
        status_match = RELEASE_TASK_FRONTMATTER_STATUS_RE.search(frontmatter)
        if not status_match or status_match.group(1).strip() != "done":
            pending.append(path.stem)
    return (len(pending) == 0, pending)


def _version_ready(
    changelog_dir: Path,
    tasks_dir: Path,
    version: str,
) -> tuple[bool, str, str]:
    """Check whether *version* is ready to release.

    Returns (ready, tag, reason).
    - ready: True when not already released and all tasks are done.
    - tag: the git tag string from the changelog.
    - reason: human-readable explanation for the readiness verdict.
    """
    try:
        content = _read_changelog(changelog_dir, version)
    except NightshiftError as exc:
        return False, version, str(exc)

    if _is_already_released(content):
        return False, version, f"{version} is already released"

    tag = _extract_tag(content, version)
    if not RELEASE_SAFE_TAG_RE.match(tag):
        raise NightshiftError(f"Invalid tag: {tag}")
    task_files = _tasks_for_version(tasks_dir, version)

    if not task_files:
        return False, tag, f"No tasks found targeting {version} -- cannot confirm readiness"

    all_done, pending = _all_tasks_done(task_files)
    if not all_done:
        pending_str = ", ".join(f"#{t}" for t in pending)
        return False, tag, f"{len(pending)} task(s) not done: {pending_str}"

    return True, tag, f"All {len(task_files)} task(s) done"


def _create_tag(repo_dir: Path, tag: str) -> None:
    """Create an annotated git tag at HEAD."""
    git(repo_dir, "tag", "-a", tag, "-m", f"Release {tag}")


def _push_tag(repo_dir: Path, tag: str) -> None:
    """Push *tag* to the remote."""
    git(repo_dir, "push", "origin", tag)


def _create_github_release(repo_dir: Path, tag: str, changelog_content: str) -> str:
    """Create a GitHub release and return the release URL.

    Raises NightshiftError if the gh CLI is not available or the command fails.
    """
    try:
        url = run_capture(
            [
                "gh",
                "release",
                "create",
                tag,
                "--title",
                tag,
                "--notes",
                changelog_content,
            ],
            cwd=repo_dir,
            timeout=60,
        )
    except NightshiftError as exc:
        raise NightshiftError(f"gh release create failed for {tag}: {exc}") from exc
    return url.strip()


def check_and_release(
    repo_dir: Path,
    *,
    version: str | None = None,
    dry_run: bool = False,
) -> ReleaseResult:
    """Check whether a version milestone is ready and optionally create a release.

    Parameters
    ----------
    repo_dir:
        Root directory of the repository.  ``.recursive/`` must exist here.
    version:
        Explicit version to check (e.g. ``"v0.0.8"``).  When *None*, the
        highest version whose changelog status is not "Released" is used.
    dry_run:
        When True, report what would be released without creating any tag or
        GitHub release.

    Returns
    -------
    ReleaseResult
        A structured dict with keys: released, version, tag, release_url, reason.
    """
    if version is not None and not RELEASE_SAFE_TAG_RE.match(version):
        raise NightshiftError(f"Invalid version format: {version}")

    changelog_dir = _changelog_dir(repo_dir)
    tasks_dir_path = _tasks_dir(repo_dir)

    if not changelog_dir.exists():
        return ReleaseResult(
            released=False,
            version=version or "",
            tag="",
            release_url="",
            reason=f"Changelog directory not found: {changelog_dir}",
        )

    # Resolve the version to check.
    if version is None:
        candidates = _list_versions(changelog_dir)
        unreleased = []
        for v in candidates:
            try:
                content = _read_changelog(changelog_dir, v)
            except NightshiftError:
                continue
            if not _is_already_released(content):
                unreleased.append(v)
        if not unreleased:
            return ReleaseResult(
                released=False,
                version="",
                tag="",
                release_url="",
                reason="No unreleased versions found in changelog",
            )
        version = unreleased[-1]  # highest unreleased version

    ready, tag, reason = _version_ready(changelog_dir, tasks_dir_path, version)

    if not ready:
        return ReleaseResult(
            released=False,
            version=version,
            tag=tag,
            release_url="",
            reason=reason,
        )

    # Read changelog content for the release notes.
    changelog_content = _read_changelog(changelog_dir, version)

    if dry_run:
        return ReleaseResult(
            released=False,
            version=version,
            tag=tag,
            release_url="",
            reason=f"[dry-run] Would release {tag} -- {reason}",
        )

    # Perform the release.
    _create_tag(repo_dir, tag)
    _push_tag(repo_dir, tag)
    release_url = _create_github_release(repo_dir, tag, changelog_content)

    return ReleaseResult(
        released=True,
        version=version,
        tag=tag,
        release_url=release_url,
        reason=reason,
    )


def find_releasable_version(repo_dir: Path) -> str | None:
    """Return the highest version ready to release, or None.

    A version is releasable when it is not already released and all tasks
    targeting it are done.  Returns ``None`` when nothing is ready.
    """
    changelog_dir = _changelog_dir(repo_dir)
    tasks_dir_path = _tasks_dir(repo_dir)

    if not changelog_dir.exists():
        return None

    for version in reversed(_list_versions(changelog_dir)):
        try:
            content = _read_changelog(changelog_dir, version)
        except NightshiftError:
            continue
        if _is_already_released(content):
            continue
        ready, _tag, _reason = _version_ready(changelog_dir, tasks_dir_path, version)
        if ready:
            return version

    return None


def _parse_version_tuple(version: str) -> tuple[int, ...]:
    """Parse a version string like 'v0.0.8' into a sortable tuple."""
    nums = re.findall(r"\d+", version)
    return tuple(int(n) for n in nums)


__all__ = [
    "check_and_release",
    "find_releasable_version",
]
