"""Entry point: PYTHONPATH=src uv run python -m tests.demo"""

import asyncio

from tests.demo.loop import Agent


def main():
    agent = Agent()
    asyncio.run(agent.chat_loop())


if __name__ == "__main__":
    main()
