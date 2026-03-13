"""Entry point: PYTHONPATH=src uv run python -m tests.demo.workflow"""

import asyncio

from tests.demo.workflow.graph import chat_loop

if __name__ == "__main__":
    asyncio.run(chat_loop())
