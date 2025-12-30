#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/src}"

OUTPUT_DIR="$ROOT_DIR/output"
mkdir -p "$OUTPUT_DIR"

export COVERAGE_FILE="$OUTPUT_DIR/.coverage"

PYTEST_ARGS=(
  "src/tests"
  "-q"
  "--cov=user.service"
  "--cov-report=term-missing"
  "--cov-report=xml:$OUTPUT_DIR/coverage.xml"
  "--junitxml=$OUTPUT_DIR/junit.xml"
)

set +e
OUTPUT="$(uv run pytest "${PYTEST_ARGS[@]}" 2>&1)"
STATUS=$?
set -e

echo "$OUTPUT" > "$OUTPUT_DIR/pytest.log"
echo "$OUTPUT"

SUMMARY_LINE="$(echo "$OUTPUT" | grep -E '^[0-9]+ (passed|failed|skipped|xfailed|xpassed|error|errors)' | tail -n 1)"
if [[ -n "${SUMMARY_LINE:-}" ]]; then
  echo
  echo "测试汇总: $SUMMARY_LINE"
fi

COVERAGE_TOTAL="$(echo "$OUTPUT" | awk '/^TOTAL/ {print $NF}' | tail -n 1)"
if [[ -n "${COVERAGE_TOTAL:-}" ]]; then
  echo "覆盖率(TOTAL): $COVERAGE_TOTAL"
fi

if [[ $STATUS -ne 0 ]]; then
  exit $STATUS
fi
