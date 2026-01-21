#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Running ruff check ==="
uv run ruff check src tests

echo ""
echo "=== Running ruff format check ==="
uv run ruff format --check src tests

echo ""
echo "=== Running mypy ==="
uv run mypy src

echo ""
echo "=== All checks passed ==="
