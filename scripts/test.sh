#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR
cd "$ROOT_DIR"

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/src}"

OUTPUT_DIR="$ROOT_DIR/output"
mkdir -p "$OUTPUT_DIR"
export COVERAGE_FILE="$OUTPUT_DIR/.coverage"

# Helper function to calculate success rate
calc_success_rate() {
    local output="$1"
    uv run python -c "
import re
import sys

text = sys.stdin.read()
ansi = re.compile(r'\x1b\[[0-9;]*m')

def norm(s):
    return ansi.sub('', s.replace('\r', '').strip())

summary = [norm(line) for line in text.splitlines()
           if re.match(r'^[0-9]+\s+(passed|failed|skipped|xfailed|xpassed|error|errors)\b', norm(line))]

if not summary:
    print('0/0 (0.00%)')
    sys.exit(0)

line = summary[-1]
items = re.findall(r'([0-9]+)\s+(passed|failed|errors?|skipped|xfailed|xpassed)\b', line)
counts = {}
for n, k in items:
    counts[k] = counts.get(k, 0) + int(n)

passed = counts.get('passed', 0)
failed = counts.get('failed', 0)
errors = counts.get('error', 0) + counts.get('errors', 0)
total = passed + failed + errors
rate = (passed / total * 100.0) if total else 0.0
print(f'{passed}/{total} ({rate:.2f}%)')
" <<< "$output"
}

echo "========================================"
echo "Running Unit Tests"
echo "========================================"

set +e
UNIT_OUTPUT="$(uv run --extra dev pytest tests/unit -q \
    --cov=src \
    --cov-report=xml:$OUTPUT_DIR/coverage.xml \
    --cov-report= \
    --junitxml=$OUTPUT_DIR/junit-unit.xml 2>&1)"
UNIT_STATUS=$?
set -e

echo "$UNIT_OUTPUT"
echo "$UNIT_OUTPUT" > "$OUTPUT_DIR/pytest-unit.log"

UNIT_RATE=$(calc_success_rate "$UNIT_OUTPUT")

echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"

echo "Unit Tests: $UNIT_RATE"

if [[ $UNIT_STATUS -ne 0 ]]; then
    echo ""
    echo "Unit tests FAILED"
    exit $UNIT_STATUS
fi

echo ""
echo "All tests PASSED"

echo ""
echo "========================================"
echo "Incremental Coverage (diff vs origin/master)"
echo "========================================"

uv run python -c "
import subprocess
import sys
import os
import yaml

with open('tests/cfg.yml', 'r') as f:
    cfg = yaml.safe_load(f) or {}

cov_cfg = cfg.get('coverage', {})
threshold = cov_cfg.get('threshold', 80)
include_patterns = cov_cfg.get('include', [])
exclude_patterns = cov_cfg.get('exclude', [])
if isinstance(include_patterns, str):
    include_patterns = [include_patterns]
if isinstance(exclude_patterns, str):
    exclude_patterns = [exclude_patterns]

# Check whether origin/master is reachable (not always true in offline / fresh clones)
probe = subprocess.run(
    ['git', 'rev-parse', '--verify', 'origin/master'],
    capture_output=True,
)
if probe.returncode != 0:
    print('origin/master not found — skipping incremental coverage check.')
    sys.exit(0)

# If HEAD == origin/master there are no new lines; nothing to enforce.
diff_check = subprocess.run(
    ['git', 'diff', '--quiet', 'HEAD', 'origin/master'],
    capture_output=True,
)
if diff_check.returncode == 0:
    print('No changes versus origin/master — skipping incremental coverage check.')
    sys.exit(0)

cmd = [
    'diff-cover', 'output/coverage.xml',
    '--compare-branch=origin/master',
    f'--fail-under={threshold}',
]
if include_patterns:
    cmd.append('--include')
    cmd.extend(include_patterns)
if exclude_patterns:
    cmd.append('--exclude')
    cmd.extend(exclude_patterns)

result = subprocess.run(cmd)
sys.exit(result.returncode)
"
