#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/src}"
export PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"
export PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-mirrors.aliyun.com}"
export UV_INDEX_URL="${UV_INDEX_URL:-https://mirrors.aliyun.com/pypi/simple/}"

if ! command -v uv >/dev/null 2>&1; then
  python -m pip install --user -i "$PIP_INDEX_URL" --trusted-host "$PIP_TRUSTED_HOST" uv
  export PATH="$HOME/.local/bin:$PATH"
fi

uv sync --frozen

uv run python -m compileall src

uv run python -c "from conf.alembic_runner import upgrade_head; upgrade_head()"

CI_CONFIG_PATH="${CI_CONFIG_PATH:-$ROOT_DIR/pipeline/ci.yml}"
export ROOT_DIR CI_CONFIG_PATH

OUTPUT_DIR="$ROOT_DIR/output"
mkdir -p "$OUTPUT_DIR"

export COVERAGE_FILE="$OUTPUT_DIR/.coverage"

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
config_path = os.environ["CI_CONFIG_PATH"]

with open(config_path, "r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f) or {}

cov_cfg = cfg.get("coverage") or {}

def as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)

threshold = float(cov_cfg.get("threshold", os.getenv("MIN_COVERAGE", "80")))
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
    rel = file_path[len(src_dir) :]
    modules.append(rel[:-3].replace(os.sep, "."))

if not modules:
    modules = ["src"]

print(threshold)
for mod in modules:
    print(mod)
PY
)"

_COV_LINES=()
while IFS= read -r _line; do
  _COV_LINES+=("$_line")
done <<< "$_CONFIG_OUTPUT"

COVERAGE_THRESHOLD="${_COV_LINES[0]}"
export COVERAGE_THRESHOLD
SERVICE_COV_ARGS=()
for module in "${_COV_LINES[@]:1}"; do
  SERVICE_COV_ARGS+=("--cov=$module")
done

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
  echo "Test summary: $SUMMARY_LINE"
fi

COVERAGE_TOTAL="$(echo "$OUTPUT" | awk '/^TOTAL/ {print $NF}' | tail -n 1)"

if [[ $STATUS -ne 0 ]]; then
  exit $STATUS
fi

python - <<'PY'
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

minimum = float(os.getenv("COVERAGE_THRESHOLD", "80"))
xml_path = os.path.join(os.getcwd(), "output", "coverage.xml")

tree = ET.parse(xml_path)
root = tree.getroot()

line_rate = root.attrib.get("line-rate")
if line_rate is None:
    raise SystemExit("coverage.xml missing line-rate")

coverage = float(line_rate) * 100.0
print(f"coverage(total): {coverage:.2f}%")

if coverage + 1e-9 < minimum:
    raise SystemExit(f"coverage gate failed: {coverage:.2f}% < {minimum:.2f}%")
PY
