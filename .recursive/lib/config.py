"""Project configuration for the Recursive daemon.

Reads .recursive.json  from the target repo.
Standalone -- no dependency on target project code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "agent": "claude",
    "cycles": 3,
    "cycle_minutes": 45,
    "eval_frequency": 5,
    "test_target": "",
    "verify_command": "",
}


def merge_config(repo_dir: str | Path) -> dict[str, Any]:
    """Read project config and merge with defaults.

    Reads .recursive.json from the target repo.
    """
    config = dict(DEFAULT_CONFIG)
    repo = Path(repo_dir)

    for name in (".recursive.json",):
        cfg_path = repo / name
        if cfg_path.exists():
            try:
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    config.update(data)
                break
            except (json.JSONDecodeError, OSError):
                pass

    return config
