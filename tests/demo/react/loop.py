"""Minimal ReACT agent loop for validating LLMClient."""

from __future__ import annotations

import asyncio
import json

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field
from tests.demo.tools import ToolRegistry, default_registry

from common.llm import LLMClient

SYSTEM_PROMPT = """\
You are a helpful assistant with access to tools.
Use tools when needed to answer questions accurately.
Always reason step by step before acting.
"""

MAX_ITERATIONS = 10
MAX_HISTORY = 20

# ANSI colors
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _separator(label: str, color: str = DIM) -> None:
    print(f"{color}{'─' * 60}{RESET}")
    print(f"{color}{label}{RESET}")
    print(f"{color}{'─' * 60}{RESET}")


class Agent:
    """Simple ReACT agent for local validation of LLMClient."""

    def __init__(
        self,
        llm: LLMClient | None = None,
        tools: ToolRegistry | None = None,
        max_iterations: int = MAX_ITERATIONS,
    ):
        self.llm = llm or LLMClient()
        self.tools = tools or default_registry()
        self.max_iterations = max_iterations
        self.history: list[BaseMessage] = []

    async def run(self, user_input: str) -> str:
        """Run one turn of the agent and return the final text response."""
        messages: list[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        messages.extend(self.history)
        messages.append(HumanMessage(content=user_input))

        tool_defs = self.tools.definitions()

        for iteration in range(self.max_iterations):
            _separator(f"Iteration {iteration + 1}/{self.max_iterations}", DIM)

            result = await self.llm.chat(messages, tools=tool_defs, tool_choice="auto")

            # Debug: show raw message fields for understanding model behavior
            raw = result.message
            extra = {
                k: v for k, v in raw.additional_kwargs.items() if k not in ("tool_calls", "refusal") and v is not None
            }
            if extra:
                print(f"{DIM}[Raw additional_kwargs] {json.dumps(extra, ensure_ascii=False, default=str)[:300]}{RESET}")

            # Show reasoning / content if present alongside tool calls
            if result.content:
                label = "[Reasoning]" if result.tool_calls else "[Content]"
                print(f"{CYAN}{label}{RESET}")
                print(f"{CYAN}{result.content}{RESET}")
                print()
            elif result.tool_calls:
                print(f"{DIM}[Reasoning] (empty - model did not output reasoning with tool calls){RESET}")
                print()

            if not result.tool_calls:
                _separator("Final Answer", GREEN)
                print(f"{GREEN}{BOLD}{result.content}{RESET}")
                print()

                # Save to conversation history
                self.history.append(HumanMessage(content=user_input))
                self.history.append(AIMessage(content=result.content))
                if len(self.history) > MAX_HISTORY:
                    self.history = self.history[-MAX_HISTORY:]
                return result.content

            # Show and execute each tool call
            messages.append(result.message)

            for i, tc in enumerate(result.tool_calls):
                print(f"{YELLOW}[Tool Call {i + 1}]{RESET} {BOLD}{tc.name}{RESET}")
                print(f"{YELLOW}  args: {json.dumps(tc.args, ensure_ascii=False)}{RESET}")
                print()

                output = self.tools.execute(tc.name, tc.args)

                print(f"{MAGENTA}[Tool Result]{RESET}")
                # Show full output but cap at 500 chars for readability
                display = output if len(output) <= 500 else output[:500] + f"\n  ... ({len(output)} chars total)"
                for line in display.splitlines():
                    print(f"{MAGENTA}  {line}{RESET}")
                print()

                messages.append(ToolMessage(content=output, tool_call_id=tc.id))

        _separator("Max iterations reached", RED)
        return "(max iterations reached)"

    async def run_structured_demo(self, user_input: str) -> None:
        """Demo structured output: extracts entities from user text."""

        class Entity(BaseModel):
            name: str = Field(description="Entity name")
            type: str = Field(description="Entity type, e.g. person, place, org, concept")
            description: str = Field(description="Brief description")

        class Extraction(BaseModel):
            entities: list[Entity] = Field(description="Extracted entities")
            summary: str = Field(description="One-sentence summary of the text")

        _separator("Structured Output Demo", CYAN)
        print(f"{DIM}Schema: Extraction(entities=[Entity(name, type, description)], summary){RESET}\n")

        messages = [
            SystemMessage(
                content="Extract all entities and provide a summary. Respond in the same language as the input."
            ),
            HumanMessage(content=user_input),
        ]
        result = await self.llm.chat_structured(messages, schema=Extraction)

        if result.data:
            print(f"{GREEN}[Parsed]{RESET} {type(result.data).__name__}")
            print(f"{GREEN}  summary:{RESET} {result.data.summary}")
            for e in result.data.entities:
                print(f"{YELLOW}  - {e.name}{RESET} ({e.type}): {e.description}")
        else:
            print(f"{RED}[No data] tool_calls={result.tool_calls}{RESET}")
        print()

    def clear(self) -> None:
        self.history.clear()

    async def chat_loop(self) -> None:
        """Interactive REPL for manual testing."""
        print(f"{BOLD}Agent ready.{RESET}")
        print("  'quit'                 - exit")
        print("  '/clear'               - reset history")
        print("  '/structured <text>'   - test structured output")
        print()

        while True:
            try:
                user_input = await asyncio.to_thread(input, f"{BOLD}You:{RESET} ")
                user_input = user_input.strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye!")
                break

            if not user_input:
                continue
            if user_input.lower() == "quit":
                break
            if user_input == "/clear":
                self.clear()
                print(f"  {DIM}[cleared conversation history]{RESET}")
                continue
            if user_input.startswith("/structured "):
                await self.run_structured_demo(user_input[12:].strip())
                continue

            await self.run(user_input)
