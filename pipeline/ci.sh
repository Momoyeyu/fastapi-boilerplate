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

bash test.sh

python - <<'PY'
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

minimum = float(os.getenv("MIN_COVERAGE", "80"))
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
