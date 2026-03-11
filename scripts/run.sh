#!/bin/bash
set -e

uv run uvicorn main:app --app-dir src --reload
