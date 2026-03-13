"""Entry point: PYTHONPATH=src uv run python -m tests.demo.langgraph"""

import asyncio

from tests.demo.langgraph.graph import chat_loop

if __name__ == "__main__":
    asyncio.run(chat_loop())
