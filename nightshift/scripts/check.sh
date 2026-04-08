#!/usr/bin/env bash
# Local CI -- mirrors .github/workflows/ci.yml.
# Run this before pushing to catch issues early.
set -euo pipefail

echo "=== ruff check ==="
python3 -m ruff check nightshift/ .recursive/tests/ .recursive/engine/ .recursive/lib/

echo "=== ruff format check ==="
python3 -m ruff format --check nightshift/ .recursive/tests/ .recursive/engine/ .recursive/lib/

echo "=== mypy ==="
python3 -m mypy nightshift/
python3 -m mypy .recursive/engine/ .recursive/lib/

echo "=== pytest ==="
python3 -m pytest nightshift/tests/ .recursive/tests/ -v --tb=short

echo "=== dry-run (codex) ==="
python3 -m nightshift run --dry-run --agent codex > /dev/null

echo "=== dry-run (claude) ==="
python3 -m nightshift run --dry-run --agent claude > /dev/null

echo "=== validate artifacts ==="
python3 -c "import json, pathlib; json.loads(pathlib.Path('nightshift/schemas/nightshift.schema.json').read_text())"
python3 -c "import json, pathlib; json.loads(pathlib.Path('.nightshift.json.example').read_text())"

echo "=== shell syntax ==="
for script in nightshift/scripts/*.sh .recursive/engine/*.sh .recursive/scripts/*.sh; do
    [ -f "$script" ] && bash -n "$script"
done

echo "=== no non-ASCII in source ==="
python3 -c "
import re, sys
from pathlib import Path
non_ascii = re.compile(r'[^\x00-\x7E]')
files = list(Path('nightshift').rglob('*.py')) + list(Path('.recursive/tests').rglob('*.py'))
files += list(Path('.recursive/engine').glob('*.py')) + list(Path('.recursive/lib').glob('*.py'))
files += sorted(Path('nightshift/scripts').glob('*.sh'))
files += [Path('pyproject.toml')]
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
content = Path('nightshift/scripts/install.sh').read_text()
files = re.findall(r'^  \"((?:nightshift/|.recursive/)?[A-Za-z_.][^\"]*\.(?:py|sh|md|json|example))\"', content, re.MULTILINE)
missing = [f for f in files if not Path(f).exists()]
if missing:
    print('Missing files referenced in install.sh:', missing)
    sys.exit(1)
print(f'All {len(files)} file references in install.sh verified.')
"

echo ""
echo "=== All checks passed ==="
