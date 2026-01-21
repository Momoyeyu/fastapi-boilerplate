#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Running ruff check ==="
uv run ruff check src tests

echo ""
echo "=== Running ruff format check ==="
if ! uv run ruff format --check src tests; then
    read -rn1 -p "Format check failed. Run ruff format? [y/n] " answer
    echo
    if [[ "$answer" == [yY] ]]; then
        echo "Formatting..."
        uv run ruff format src tests
        echo "Format complete."
    else
        echo "Skipped formatting."
        exit 1
    fi
fi

echo ""
echo "=== Running mypy ==="
uv run mypy src

echo ""
echo "=== All checks passed ==="
