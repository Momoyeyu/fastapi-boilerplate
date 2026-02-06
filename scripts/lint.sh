#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "=== Running ruff check ==="
if ! uv run ruff check src tests; then
    read -rn1 -p "Lint check failed. Run ruff check --fix? [y/n] " answer
    echo
    if [[ "$answer" == [yY] ]]; then
        uv run ruff check --fix src tests
        echo "Fix complete."
    else
        echo "Skipped fix."
        exit 1
    fi
fi

echo ""
echo "=== Running ruff format check ==="
if ! uv run ruff format --check src tests; then
    read -rn1 -p "Format check failed. Run ruff format? [y/n] " answer
    echo
    if [[ "$answer" == [yY] ]]; then
        uv run ruff format src tests
        echo "Format complete."
    else
        echo "Skipped formatting."
        exit 1
    fi
fi

echo ""
echo "=== All checks passed ==="
