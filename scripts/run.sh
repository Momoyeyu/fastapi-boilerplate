#!/bin/bash
set -e

cd "$(dirname "$0")"

./migrate.sh

uv run uvicorn main:app --app-dir src --reload
