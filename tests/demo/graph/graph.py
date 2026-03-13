"""LangGraph workflow demo: intent classification → conditional routing.

Demonstrates how LLMClient integrates with LangGraph:
- chat_structured() for intent classification
- model property for create_react_agent
- chat() for direct LLM nodes (translate, summarize)
"""

from __future__ import annotations

import asyncio
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from tests.demo.tools import as_langchain_tools
from typing_extensions import TypedDict

from common.llm import LLMClient

# ANSI colors
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
MAGENTA = "\033[35m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class GraphState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    intent: str


# ---------------------------------------------------------------------------
# Intent schema
# ---------------------------------------------------------------------------


class Intent(BaseModel):
    intent: Literal["agent", "translate", "summarize"] = Field(
        description=(
            "Classify: 'agent' for questions needing tools (time, math, shell), "
            "'translate' for translation requests, "
            "'summarize' for summarization requests."
        ),
    )
    reasoning: str = Field(description="Brief reasoning for the classification")


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


def build_graph(client: LLMClient) -> StateGraph:
    """Build and compile the intent-routing graph."""

    react_agent = create_react_agent(client.model, as_langchain_tools())

    async def classify(state: GraphState) -> dict:
        """Classify user intent via structured output."""
        last_msg = state["messages"][-1]
        result = await client.chat_structured(
            [
                SystemMessage(content="Classify the user's intent. Respond in the requested language."),
                last_msg,
            ],
            schema=Intent,
        )
        intent = result.data.intent if result.data else "agent"
        reasoning = result.data.reasoning if result.data else ""
        print(f"{DIM}[classify] intent={intent}  reasoning={reasoning}{RESET}")
        return {"intent": intent}

    def route(state: GraphState) -> Literal["react_node", "translate_node", "summarize_node"]:
        mapping = {"agent": "react_node", "translate": "translate_node", "summarize": "summarize_node"}
        return mapping.get(state["intent"], "react_node")

    async def react_node(state: GraphState) -> dict:
        """Route to the prebuilt ReACT agent with tools."""
        print(f"{YELLOW}[react] invoking agent with tools ...{RESET}")
        result = await react_agent.ainvoke({"messages": state["messages"]})
        return {"messages": result["messages"]}

    async def translate_node(state: GraphState) -> dict:
        """Direct LLM call for translation."""
        print(f"{CYAN}[translate] translating ...{RESET}")
        result = await client.chat(
            [
                SystemMessage(
                    content=(
                        "You are a translator. Translate the user's text. "
                        "If the text is in Chinese, translate to English; otherwise translate to Chinese. "
                        "Output ONLY the translated text."
                    ),
                ),
                state["messages"][-1],
            ],
        )
        return {"messages": [AIMessage(content=result.content)]}

    async def summarize_node(state: GraphState) -> dict:
        """Direct LLM call for summarization."""
        print(f"{MAGENTA}[summarize] summarizing ...{RESET}")
        result = await client.chat(
            [
                SystemMessage(
                    content=(
                        "You are a summarizer. Provide a concise summary of the user's text. "
                        "Respond in the same language as the input."
                    ),
                ),
                state["messages"][-1],
            ],
        )
        return {"messages": [AIMessage(content=result.content)]}

    # -- Build graph --
    builder = StateGraph(GraphState)
    builder.add_node("classify", classify)
    builder.add_node("react_node", react_node)
    builder.add_node("translate_node", translate_node)
    builder.add_node("summarize_node", summarize_node)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route,
        {"react_node": "react_node", "translate_node": "translate_node", "summarize_node": "summarize_node"},
    )
    builder.add_edge("react_node", END)
    builder.add_edge("translate_node", END)
    builder.add_edge("summarize_node", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Chat loop
# ---------------------------------------------------------------------------


async def chat_loop() -> None:
    client = LLMClient()
    graph = build_graph(client)

    print(f"{BOLD}LangGraph Workflow Demo{RESET}")
    print(f"  Intents: {GREEN}agent{RESET} (tools) | {CYAN}translate{RESET} | {MAGENTA}summarize{RESET}")
    print("  'quit' to exit")
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

        result = await graph.ainvoke({"messages": [HumanMessage(content=user_input)], "intent": ""})

        # Print the last AI message
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                print()
                print(f"{GREEN}{BOLD}{msg.content}{RESET}")
                print()
                break
