#!/bin/bash
set -e

cd "$(dirname "$0")/.."

# Load environment variables from .env if it exists
if [ -f .env ]; then
    set -a
    . .env
    set +a
fi

uv run uvicorn main:app --app-dir src --reload \
    --host "${SERVER_HOST:-localhost}" \
    --port "${SERVER_PORT:-8000}"
