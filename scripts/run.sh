#!/bin/bash
set -e

cd "$(dirname "$0")/.."

./scripts/migrate.sh

uv run uvicorn main:app --app-dir src --reload
