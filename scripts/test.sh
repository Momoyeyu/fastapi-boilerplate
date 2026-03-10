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
echo "Running Integration Tests"
echo "========================================"

set +e
INT_OUTPUT="$(uv run --extra dev pytest tests/integration -q \
    --junitxml=$OUTPUT_DIR/junit-integration.xml 2>&1)"
INT_STATUS=$?
set -e

echo "$INT_OUTPUT"
echo "$INT_OUTPUT" > "$OUTPUT_DIR/pytest-integration.log"

INT_RATE=$(calc_success_rate "$INT_OUTPUT")

echo ""
echo "========================================"
echo "Test Summary"
echo "========================================"

echo "Unit Tests:        $UNIT_RATE"
echo "Integration Tests: $INT_RATE"

# Exit with failure if any tests failed
if [[ $UNIT_STATUS -ne 0 ]]; then
    echo ""
    echo "Unit tests FAILED"
    exit $UNIT_STATUS
fi

if [[ $INT_STATUS -ne 0 ]]; then
    echo ""
    echo "Integration tests FAILED"
    exit $INT_STATUS
fi

echo ""
echo "All tests PASSED"

echo ""
echo "========================================"
echo "Coverage Report"
echo "========================================"

uv run python -c "
import subprocess
import sys
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

cmd = ['uv', 'run', 'coverage', 'report']
if include_patterns:
    cmd.append('--include=' + ','.join(include_patterns))
if exclude_patterns:
    cmd.append('--omit=' + ','.join(exclude_patterns))

result = subprocess.run(cmd)

# Check threshold
cmd_json = ['uv', 'run', 'coverage', 'json', '-o', '/dev/stdout', '-q']
if include_patterns:
    cmd_json.append('--include=' + ','.join(include_patterns))
if exclude_patterns:
    cmd_json.append('--omit=' + ','.join(exclude_patterns))

import json
out = subprocess.run(cmd_json, capture_output=True, text=True)
if out.returncode == 0:
    data = json.loads(out.stdout)
    pct = data.get('totals', {}).get('percent_covered', 0)
    print()
    if pct >= threshold:
        print(f'Coverage: {pct:.1f}% (threshold: {threshold}%) ✓')
    else:
        print(f'Coverage: {pct:.1f}% (threshold: {threshold}%) ✗')
        sys.exit(1)
"
