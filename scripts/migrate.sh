#!/bin/bash
set -e

cd "$(dirname "$0")/.."

echo "Running database migrations..."

# Use uv run locally, direct python in Docker (where PYTHONPATH is already set)
if [ -n "$PYTHONPATH" ]; then
    python -c "from migration.runner import upgrade_head; upgrade_head()"
else
    uv run python -c "import sys; sys.path.insert(0, 'src'); from migration.runner import upgrade_head; upgrade_head()"
fi

echo "Database migrations completed."
