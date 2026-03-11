#!/bin/bash
set -e

cd "$(dirname "$0")/.."

uv run uvicorn main:app --app-dir src --reload
