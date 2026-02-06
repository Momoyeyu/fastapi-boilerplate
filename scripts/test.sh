#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR
cd "$ROOT_DIR"

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/src}"

OUTPUT_DIR="$ROOT_DIR/output"
mkdir -p "$OUTPUT_DIR"

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
