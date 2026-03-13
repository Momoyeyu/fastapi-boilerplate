"""Entry point: PYTHONPATH=src uv run python -m tests.demo.graph"""

import asyncio

from tests.demo.graph.graph import chat_loop

if __name__ == "__main__":
    asyncio.run(chat_loop())
