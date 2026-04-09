"""Known evaluation targets and their repo-specific verification settings."""

from __future__ import annotations

import configparser
from pathlib import Path
from urllib.parse import urlsplit

# Canonical URL for the primary evaluation target used in nightshift test runs.
PHRACTAL_URL = "https://github.com/fazxes/Phractal"

_KNOWN_TARGET_VERIFY_COMMANDS: dict[str, str] = {
    "github.com/fazxes/phractal": "python3 -m compileall apps/api/app",
}


def _git_config_path(repo_dir: Path) -> Path | None:
    git_path = repo_dir / ".git"
    if git_path.is_dir():
        config_path = git_path / "config"
        return config_path if config_path.is_file() else None
    if not git_path.is_file():
        return None

    try:
        content = git_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not content.startswith("gitdir:"):
        return None

    git_dir = Path(content.split(":", 1)[1].strip())
    if not git_dir.is_absolute():
        git_dir = (repo_dir / git_dir).resolve()

    common_dir_path = git_dir / "commondir"
    if common_dir_path.is_file():
        try:
            common_dir = Path(common_dir_path.read_text(encoding="utf-8").strip())
        except OSError:
            common_dir = Path()
        if common_dir and not common_dir.is_absolute():
            common_dir = (git_dir / common_dir).resolve()
        config_path = common_dir / "config"
        if config_path.is_file():
            return config_path

    config_path = git_dir / "config"
    return config_path if config_path.is_file() else None


def _origin_remote_url(repo_dir: Path) -> str | None:
    config_path = _git_config_path(repo_dir)
    if config_path is None:
        return None

    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read(config_path, encoding="utf-8")
    except configparser.Error:
        return None
    if not parser.has_section('remote "origin"'):
        return None
    return parser.get('remote "origin"', "url", fallback=None)


def _normalize_remote_url(url: str) -> str | None:
    raw = url.strip()
    if not raw:
        return None

    if raw.startswith("git@"):
        host_path = raw.removeprefix("git@")
        if ":" not in host_path:
            return None
        host, path = host_path.split(":", 1)
    else:
        split = urlsplit(raw)
        if not split.netloc:
            return None
        host = split.netloc.rsplit("@", 1)[-1]
        path = split.path

    normalized_path = path.strip("/").removesuffix(".git")
    if not normalized_path:
        return None
    return f"{host.lower()}/{normalized_path.lower()}"


def infer_target_verify_command(repo_dir: Path) -> str | None:
    """Return a repo-specific verify command for known evaluation targets."""
    remote_url = _origin_remote_url(repo_dir)
    if remote_url is None:
        return None

    remote_key = _normalize_remote_url(remote_url)
    if remote_key is None:
        return None
    return _KNOWN_TARGET_VERIFY_COMMANDS.get(remote_key)
