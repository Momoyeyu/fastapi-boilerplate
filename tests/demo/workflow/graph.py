"""LangGraph workflow demo: intent classification → conditional routing.

Demonstrates how LLMClient integrates with LangGraph:
- chat_structured() for intent classification
- model property for create_react_agent
- chat() for direct LLM nodes (translate, summarize)
- Multi-step chains: translate → polish, summarize → extract keywords

Graph:
    START → classify ─┬─→ react_node ─────────────────────────────→ END
                      ├─→ plan_translate → translate → polish ────→ END
                      └─→ summarize_node → keyword_node ──────────→ END
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
BLUE = "\033[34m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

_ARROW = f"{DIM}→{RESET}"


def _node_enter(name: str, color: str, detail: str = "") -> None:
    suffix = f"  {DIM}{detail}{RESET}" if detail else ""
    print(f"\n{color}{BOLD}[{name}]{RESET}{suffix}")


def _node_exit(name: str, color: str, output_preview: str) -> None:
    lines = output_preview.strip().splitlines()
    preview = lines[0][:120] + (" ..." if len(lines) > 1 or len(lines[0]) > 120 else "")
    print(f"{color}  ╰─ {preview}{RESET}")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class GraphState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    intent: str
    translate_segments: list[str]
    translated_text: str
    summary_text: str


# ---------------------------------------------------------------------------
# Intent schema
# ---------------------------------------------------------------------------

CLASSIFY_PROMPT = """\
You are the router of an AI assistant. Classify the user's intent into ONE of:

- "agent":     The user asks a question that needs tools to answer.
               Available tools: clock (current date/time), calc (math expressions), shell (run commands).
               Examples: "What time is it?", "Calculate 2^10", "List files in current dir"
- "translate": The user wants text translated between languages.
               Examples: "Translate this to English", "把这段翻译成中文"
- "summarize": The user wants a piece of text summarized or condensed.
               Examples: "Summarize the following article", "帮我总结一下这段话"

If uncertain, default to "agent".
Respond with JSON only."""


class Intent(BaseModel):
    intent: Literal["agent", "translate", "summarize"] = Field(
        description="One of: agent, translate, summarize",
    )
    reasoning: str = Field(description="Brief reasoning for the classification")


class TranslationPlan(BaseModel):
    source_lang: str = Field(description="Detected source language, e.g. 'Chinese', 'English'")
    target_lang: str = Field(description="Target language to translate into")
    segments: list[str] = Field(
        description="The text split into logical segments for batch translation (by paragraph or sentence group)",
    )


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_graph(client: LLMClient) -> StateGraph:
    """Build and compile the intent-routing graph."""

    react_agent = create_react_agent(client.model, as_langchain_tools())

    # -- classify ----------------------------------------------------------

    async def classify(state: GraphState) -> dict:
        last_msg = state["messages"][-1]
        _node_enter("classify", DIM, f"input: {last_msg.content[:80]}")

        result = await client.chat_structured(
            [SystemMessage(content=CLASSIFY_PROMPT), last_msg],
            schema=Intent,
        )
        intent = result.data.intent if result.data else "agent"
        reasoning = result.data.reasoning if result.data else ""

        _node_exit("classify", DIM, f"intent={intent}  reason={reasoning}")
        return {"intent": intent}

    def route(state: GraphState) -> Literal["react_node", "plan_translate", "summarize_node"]:
        mapping = {"agent": "react_node", "translate": "plan_translate", "summarize": "summarize_node"}
        dest = mapping.get(state["intent"], "react_node")
        print(f"\n{DIM}  ── routing {_ARROW} {BOLD}{dest}{RESET}")
        return dest

    # -- agent (react) -----------------------------------------------------

    async def react_node(state: GraphState) -> dict:
        _node_enter("react", YELLOW, "invoking ReACT agent with tools: clock, calc, shell")

        result = await react_agent.ainvoke({"messages": state["messages"]})

        # Show tool call trace
        for msg in result["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"{YELLOW}  ├─ tool_call: {tc['name']}({tc['args']}){RESET}")
            if msg.type == "tool":
                preview = msg.content[:100] if msg.content else "(empty)"
                print(f"{YELLOW}  ├─ tool_result: {preview}{RESET}")

        final = next((m for m in reversed(result["messages"]) if isinstance(m, AIMessage) and m.content), None)
        if final:
            _node_exit("react", YELLOW, final.content)

        return {"messages": result["messages"]}

    # -- translate chain: plan → translate → polish ----------------------

    async def plan_translate(state: GraphState) -> dict:
        user_text = state["messages"][-1].content
        _node_enter("plan", CYAN, f"analyzing text ({len(user_text)} chars)")

        result = await client.chat_structured(
            [
                SystemMessage(
                    content=(
                        "You are a translation planner. Analyze the text and produce a plan:\n"
                        "1. Detect the source language.\n"
                        "2. Decide the target language (Chinese↔English).\n"
                        "3. Split the text into logical segments for batch translation.\n"
                        "   - Short text (< 3 sentences): keep as one segment.\n"
                        "   - Longer text: split by paragraph or sentence group.\n"
                        "Each segment should be self-contained and translatable independently."
                    ),
                ),
                state["messages"][-1],
            ],
            schema=TranslationPlan,
        )
        plan = result.data
        if plan:
            print(f"{CYAN}  ├─ source: {plan.source_lang} → target: {plan.target_lang}{RESET}")
            print(f"{CYAN}  ├─ segments: {len(plan.segments)}{RESET}")
            for i, seg in enumerate(plan.segments):
                preview = seg[:60] + ("..." if len(seg) > 60 else "")
                print(f"{CYAN}  │  [{i + 1}] {preview}{RESET}")
            _node_exit("plan", CYAN, f"{len(plan.segments)} segment(s) planned")
            return {"translate_segments": plan.segments}

        _node_exit("plan", CYAN, "fallback: single segment")
        return {"translate_segments": [user_text]}

    async def translate_node(state: GraphState) -> dict:
        segments = state["translate_segments"]
        _node_enter("translate", CYAN, f"translating {len(segments)} segment(s)")

        translated_parts: list[str] = []
        for i, seg in enumerate(segments):
            result = await client.chat(
                [
                    SystemMessage(
                        content=(
                            "You are a translator. Translate the following text segment.\n"
                            "Output ONLY the translated text, no explanations or labels."
                        ),
                    ),
                    HumanMessage(content=seg),
                ],
            )
            translated_parts.append(result.content)
            print(
                f"{CYAN}  ├─ [{i + 1}/{len(segments)}] {result.content[:80]}{'...' if len(result.content) > 80 else ''}{RESET}"
            )

        translated = "\n\n".join(translated_parts)
        _node_exit("translate", CYAN, f"done ({len(translated)} chars)")
        return {"translated_text": translated}

    async def polish_node(state: GraphState) -> dict:
        raw = state["translated_text"]
        _node_enter("polish", BLUE, f"refining translation ({len(raw)} chars)")

        result = await client.chat(
            [
                SystemMessage(
                    content=(
                        "You are a translation editor. The text below is a raw translation.\n"
                        "Polish it for natural fluency while preserving the original meaning.\n"
                        "Ensure consistent tone and smooth transitions between paragraphs.\n"
                        "Output ONLY the polished text."
                    ),
                ),
                HumanMessage(content=raw),
            ],
        )
        polished = result.content
        _node_exit("polish", BLUE, polished)
        return {"messages": [AIMessage(content=polished)]}

    # -- summarize chain: summarize → extract keywords ---------------------

    async def summarize_node(state: GraphState) -> dict:
        user_text = state["messages"][-1].content
        _node_enter("summarize", MAGENTA, f"input ({len(user_text)} chars)")

        result = await client.chat(
            [
                SystemMessage(
                    content=(
                        "Provide a concise summary (2-3 sentences) of the user's text.\n"
                        "Respond in the same language as the input."
                    ),
                ),
                state["messages"][-1],
            ],
        )
        summary = result.content
        _node_exit("summarize", MAGENTA, summary)
        return {"summary_text": summary}

    async def keyword_node(state: GraphState) -> dict:
        summary = state["summary_text"]
        _node_enter("keywords", GREEN, "extracting keywords from summary")

        result = await client.chat(
            [
                SystemMessage(
                    content=(
                        "Given the summary below, extract 3-5 keywords.\n"
                        "Format: Keywords: word1, word2, word3\n"
                        "Then output the summary followed by the keywords.\n"
                        "Respond in the same language as the input."
                    ),
                ),
                HumanMessage(content=summary),
            ],
        )
        _node_exit("keywords", GREEN, result.content)
        return {"messages": [AIMessage(content=result.content)]}

    # -- build graph -------------------------------------------------------

    builder = StateGraph(GraphState)
    builder.add_node("classify", classify)
    builder.add_node("react_node", react_node)
    builder.add_node("plan_translate", plan_translate)
    builder.add_node("translate_node", translate_node)
    builder.add_node("polish_node", polish_node)
    builder.add_node("summarize_node", summarize_node)
    builder.add_node("keyword_node", keyword_node)

    builder.add_edge(START, "classify")
    builder.add_conditional_edges(
        "classify",
        route,
        {"react_node": "react_node", "plan_translate": "plan_translate", "summarize_node": "summarize_node"},
    )
    # agent → END
    builder.add_edge("react_node", END)
    # plan → translate → polish → END
    builder.add_edge("plan_translate", "translate_node")
    builder.add_edge("translate_node", "polish_node")
    builder.add_edge("polish_node", END)
    # summarize → keywords → END
    builder.add_edge("summarize_node", "keyword_node")
    builder.add_edge("keyword_node", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Chat loop
# ---------------------------------------------------------------------------


MAX_HISTORY = 20


async def chat_loop() -> None:
    client = LLMClient()
    graph = build_graph(client)
    history: list[BaseMessage] = []

    print(f"{BOLD}LangGraph Workflow Demo{RESET}")
    print(f"{DIM}{'─' * 60}{RESET}")
    print(f"  {YELLOW}agent{RESET}     — ReACT with tools (clock, calc, shell)")
    print(f"  {CYAN}translate{RESET} — plan → translate (per segment) → polish")
    print(f"  {MAGENTA}summarize{RESET} — summarize → extract keywords")
    print(f"{DIM}{'─' * 60}{RESET}")
    print("  'quit' to exit, '/clear' to reset history\n")

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
            history.clear()
            print(f"  {DIM}[cleared conversation history]{RESET}")
            continue

        print(f"\n{DIM}{'═' * 60}{RESET}")
        result = await graph.ainvoke(
            {
                "messages": history + [HumanMessage(content=user_input)],
                "intent": "",
                "translate_segments": [],
                "translated_text": "",
                "summary_text": "",
            }
        )
        print(f"{DIM}{'═' * 60}{RESET}")

        # Extract final AI answer and save to history
        answer = ""
        for msg in reversed(result["messages"]):
            if isinstance(msg, AIMessage) and msg.content:
                answer = msg.content
                print(f"\n{GREEN}{BOLD}{answer}{RESET}\n")
                break

        history.append(HumanMessage(content=user_input))
        if answer:
            history.append(AIMessage(content=answer))
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
