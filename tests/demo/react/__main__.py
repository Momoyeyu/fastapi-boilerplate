"""Entry point: PYTHONPATH=src uv run python -m tests.demo.react"""

import asyncio

from tests.demo.react.loop import Agent


def main():
    asyncio.run(Agent().chat_loop())


if __name__ == "__main__":
    main()
