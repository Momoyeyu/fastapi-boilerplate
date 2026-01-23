#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "Running database migrations..."

# Docker: PYTHONPATH is pre-configured
# Local: need to set PYTHONPATH to include src and project root
if [ -n "$PYTHONPATH" ]; then
    python -c "from migration.runner import upgrade_head; upgrade_head()"
else
    PYTHONPATH="src:." uv run python -c "from migration.runner import upgrade_head; upgrade_head()"
fi

echo "Database migrations completed."
