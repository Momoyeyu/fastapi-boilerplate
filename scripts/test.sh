#!/usr/bin/env bash
# Run all tests (unit + integration) with coverage and success rate statistics
# Configuration is read from tests/test.yml
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export ROOT_DIR
cd "$ROOT_DIR"

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/src}"

OUTPUT_DIR="$ROOT_DIR/output"
mkdir -p "$OUTPUT_DIR"

export COVERAGE_FILE="$OUTPUT_DIR/.coverage"

TEST_CONFIG_PATH="${TEST_CONFIG_PATH:-$ROOT_DIR/tests/test.yml}"

# Parse test.yml configuration
_CONFIG_OUTPUT="$(uv run python - <<'PY'
from __future__ import annotations

import glob
import os
import sys

try:
    import yaml
except Exception as e:
    raise SystemExit(f"missing yaml parser (PyYAML). import yaml failed: {e}")

root_dir = os.environ["ROOT_DIR"]
config_path = os.environ.get("TEST_CONFIG_PATH", os.path.join(root_dir, "tests", "test.yml"))

if not os.path.exists(config_path):
    # Default values if config not found
    print("80")
    print("user.service")
    print("middleware.auth")
    sys.exit(0)

with open(config_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

cov_cfg = cfg.get("coverage") or {}


def as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


threshold = float(cov_cfg.get("threshold", os.getenv("COVERAGE_THRESHOLD", "80")))
include_patterns = as_list(cov_cfg.get("include")) or ["src/**/service.py"]
exclude_patterns = as_list(cov_cfg.get("exclude"))


def expand(patterns: list[str]) -> set[str]:
    files: set[str] = set()
    for pattern in patterns:
        abs_pattern = os.path.join(root_dir, pattern)
        for path in glob.glob(abs_pattern, recursive=True):
            path = os.path.normpath(path)
            if os.path.isfile(path) and path.endswith(".py"):
                files.add(path)
    return files


include_files = expand(include_patterns)
exclude_files = expand(exclude_patterns)
selected_files = sorted(include_files - exclude_files)

src_dir = os.path.join(root_dir, "src") + os.sep
modules: list[str] = []
for file_path in selected_files:
    if not file_path.startswith(src_dir):
        continue
    rel = file_path[len(src_dir):]
    modules.append(rel[:-3].replace(os.sep, "."))

if not modules:
    modules = ["src"]

print(threshold)
for mod in modules:
    print(mod)
PY
)"

# Parse config output
_COV_LINES=()
while IFS= read -r _line; do
    _COV_LINES+=("$_line")
done <<< "$_CONFIG_OUTPUT"

COVERAGE_THRESHOLD="${_COV_LINES[0]}"
export COVERAGE_THRESHOLD

# Build coverage arguments
SERVICE_COV_ARGS=()
for module in "${_COV_LINES[@]:1}"; do
    SERVICE_COV_ARGS+=("--cov=$module")
done

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
    "${SERVICE_COV_ARGS[@]}" \
    --cov-report=term-missing \
    --cov-report=xml:$OUTPUT_DIR/coverage.xml \
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

# Extract coverage percentage
COVERAGE_PCT=$(uv run python -c "
import xml.etree.ElementTree as ET
import os

xml_path = os.path.join('$OUTPUT_DIR', 'coverage.xml')
if not os.path.exists(xml_path):
    print('N/A')
else:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    line_rate = root.attrib.get('line-rate', '0')
    coverage = float(line_rate) * 100.0
    print(f'{coverage:.2f}%')
")

echo "Unit Tests:        $UNIT_RATE"
echo "Unit Coverage:     $COVERAGE_PCT (threshold: ${COVERAGE_THRESHOLD}%)"
echo "Integration Tests: $INT_RATE"

# Check coverage threshold
uv run python -c "
import xml.etree.ElementTree as ET
import os
import sys

minimum = float('$COVERAGE_THRESHOLD')
xml_path = os.path.join('$OUTPUT_DIR', 'coverage.xml')

if not os.path.exists(xml_path):
    print('Warning: coverage.xml not found, skipping coverage check')
    sys.exit(0)

tree = ET.parse(xml_path)
root = tree.getroot()
line_rate = root.attrib.get('line-rate')
if line_rate is None:
    print('Warning: coverage.xml missing line-rate')
    sys.exit(0)

coverage = float(line_rate) * 100.0
if coverage + 1e-9 < minimum:
    print(f'Coverage gate FAILED: {coverage:.2f}% < {minimum:.2f}%')
    sys.exit(1)
else:
    print(f'Coverage gate PASSED: {coverage:.2f}% >= {minimum:.2f}%')
"

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
