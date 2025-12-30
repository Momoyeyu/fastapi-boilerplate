#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/src}"

OUTPUT_DIR="$ROOT_DIR/output"
mkdir -p "$OUTPUT_DIR"

export COVERAGE_FILE="$OUTPUT_DIR/.coverage"

SERVICE_COV_ARGS=()
while IFS= read -r file; do
  rel="${file#"$ROOT_DIR/src/"}"
  module="${rel%.py}"
  module="${module//\//.}"
  SERVICE_COV_ARGS+=("--cov=$module")
done < <(find "$ROOT_DIR/src" -type f -name "service.py" | sort)

if [[ ${#SERVICE_COV_ARGS[@]} -eq 0 ]]; then
  SERVICE_COV_ARGS+=("--cov=src")
fi

PYTEST_ARGS=("src/tests" "-q")
PYTEST_ARGS+=("${SERVICE_COV_ARGS[@]}")
PYTEST_ARGS+=(
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
