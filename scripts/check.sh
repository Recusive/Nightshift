#!/usr/bin/env bash
# Local CI -- mirrors .github/workflows/ci.yml.
# Run this before pushing to catch issues early.
set -euo pipefail

echo "=== ruff check ==="
python3 -m ruff check nightshift/ tests/

echo "=== ruff format check ==="
python3 -m ruff format --check nightshift/ tests/

echo "=== mypy ==="
python3 -m mypy nightshift/

echo "=== pytest ==="
python3 -m pytest tests/ -v --tb=short

echo "=== dry-run (codex) ==="
python3 -m nightshift run --dry-run --agent codex > /dev/null

echo "=== dry-run (claude) ==="
python3 -m nightshift run --dry-run --agent claude > /dev/null

echo "=== validate artifacts ==="
python3 -c "import json, pathlib; json.loads(pathlib.Path('nightshift.schema.json').read_text())"
python3 -c "import json, pathlib; json.loads(pathlib.Path('.nightshift.json.example').read_text())"

echo "=== shell syntax ==="
bash -n scripts/run.sh
bash -n scripts/test.sh
bash -n scripts/install.sh
bash -n scripts/check.sh

echo "=== no non-ASCII in source ==="
python3 -c "
import re, sys
from pathlib import Path
non_ascii = re.compile(r'[^\x00-\x7E]')
files = list(Path('nightshift').rglob('*.py')) + list(Path('tests').rglob('*.py'))
files += [Path(f) for f in ['scripts/check.sh', 'scripts/install.sh', 'scripts/run.sh', 'scripts/test.sh', 'pyproject.toml']]
found = []
for f in sorted(files):
    for i, line in enumerate(f.read_text().splitlines(), 1):
        for m in non_ascii.finditer(line):
            found.append(f'{f}:{i}: U+{ord(m.group()):04X} {repr(m.group())}')
if found:
    print('Non-ASCII characters found:')
    for line in found:
        print(f'  {line}')
    sys.exit(1)
print(f'All {len(files)} source files are ASCII-clean.')
"

echo "=== install.sh file refs ==="
python3 -c "
import re, sys
from pathlib import Path
content = Path('scripts/install.sh').read_text()
# Match only simple relative paths (no \$, ~, or /) at the start
files = re.findall(r'^  \"((?:nightshift/|scripts/)?[A-Za-z_.][^\"]*\.(?:py|sh|md|json|example))\"', content, re.MULTILINE)
missing = [f for f in files if not Path(f).exists()]
if missing:
    print('Missing files referenced in install.sh:', missing)
    sys.exit(1)
print(f'All {len(files)} file references in install.sh verified.')
"

echo ""
echo "=== All checks passed ==="
