#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="${PYTHONPATH:-$ROOT_DIR/src}"

set +e
OUTPUT="$(uv run pytest src/tests -q 2>&1)"
STATUS=$?
set -e

echo "$OUTPUT"

printf '%s\n' "$OUTPUT" | python -c $'import re,sys\ntext=sys.stdin.read()\nansi=re.compile(r\"\\x1b\\[[0-9;]*m\")\n\ndef norm(s):\n    return ansi.sub(\"\", s.replace(\"\\r\", \"\").strip())\n\nsummary=[norm(line) for line in text.splitlines() if re.match(r\"^[0-9]+\\s+(passed|failed|skipped|xfailed|xpassed|error|errors)\\b\", norm(line))]\nif not summary:\n    print(\"success rate: 0/0 (0.00%)\")\n    raise SystemExit(0)\nline=summary[-1]\nitems=re.findall(r\"([0-9]+)\\s+(passed|failed|errors?|skipped|xfailed|xpassed)\\b\", line)\ncounts={}\nfor n,k in items:\n    counts[k]=counts.get(k,0)+int(n)\npassed=counts.get(\"passed\",0)\nfailed=counts.get(\"failed\",0)\nerrors=counts.get(\"error\",0)+counts.get(\"errors\",0)\ntotal=passed+failed+errors\nrate=(passed/total*100.0) if total else 0.0\nprint(f\"success rate: {passed}/{total} ({rate:.2f}%)\")\n'

exit $STATUS
