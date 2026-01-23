#!/bin/bash
set -e

./scripts/migrate.sh
uv run uvicorn main:app --app-dir src --reload
