"""Entry point: PYTHONPATH=src uv run python -m tests.demo [react|workflow]"""

import asyncio
import sys


def main():
    choice = sys.argv[1] if len(sys.argv) > 1 else "react"

    if choice == "react":
        from tests.demo.react.loop import Agent

        asyncio.run(Agent().chat_loop())
    elif choice == "workflow":
        from tests.demo.workflow.graph import chat_loop

        asyncio.run(chat_loop())
    else:
        print("Usage: python -m tests.demo [react|workflow]")
        print()
        print("  react      - Manual ReACT agent loop (default)")
        print("  workflow   - LangGraph intent-routing workflow")
        sys.exit(1)


if __name__ == "__main__":
    main()
