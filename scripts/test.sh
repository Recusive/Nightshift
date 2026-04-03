#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PYTHONPATH="$REPO_DIR${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m nightshift test "$@"
