from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Generic, TypeVar

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from conf.config import settings

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Response types
# ---------------------------------------------------------------------------


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    id: str
    name: str
    args: dict[str, Any]


@dataclass
class ChatResult:
    """Result of a chat() invocation."""

    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    message: AIMessage = field(default_factory=lambda: AIMessage(content=""))


@dataclass
class StructuredChatResult(Generic[T]):
    """Result of a chat_structured() invocation."""

    data: T | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    message: AIMessage = field(default_factory=lambda: AIMessage(content=""))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_tool_calls(message: AIMessage) -> list[ToolCall]:
    """Extract ToolCall list from an AIMessage."""
    return [ToolCall(id=tc["id"], name=tc["name"], args=tc["args"]) for tc in (message.tool_calls or [])]


# ---------------------------------------------------------------------------
# Model factory
# ---------------------------------------------------------------------------


def create_chat_model(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> ChatOpenAI:
    """Create a ChatOpenAI instance from settings.

    Use this directly when you need a raw LangChain model, e.g. for LangGraph::

        from common.llm import create_chat_model
        model = create_chat_model()
        agent = create_react_agent(model, tools)
    """
    key = api_key or settings.llm_api_key.get_secret_value()
    if not key:
        raise ValueError("LLM_API_KEY is not configured")
    return ChatOpenAI(
        api_key=key,
        base_url=base_url or settings.llm_base_url,
        model=model or settings.llm_model_name,
    )


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------


class LLMClient:
    """LLM client with LangChain backend.

    Provides ``chat()`` and ``chat_structured()`` with typed results.
    For LangGraph or other frameworks that need a raw model, use
    ``create_chat_model()`` instead.
    """

    def __init__(
        self,
        llm: BaseChatModel | None = None,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.llm = llm or create_chat_model(api_key, base_url, model)

    @property
    def model(self) -> BaseChatModel:
        """The underlying LangChain model, e.g. for LangGraph integration."""
        return self.llm

    def _prepare_llm(
        self,
        tools: list | None = None,
        tool_choice: str | dict | None = None,
        response_format: type | None = None,
    ) -> BaseChatModel:
        """Bind tools to the model if provided, otherwise return as-is."""
        if not tools:
            return self.llm
        bind_kwargs: dict[str, Any] = {"parallel_tool_calls": False}
        if tool_choice:
            bind_kwargs["tool_choice"] = tool_choice
        if response_format:
            bind_kwargs["response_format"] = response_format
        return self.llm.bind_tools(tools, **bind_kwargs)

    async def chat(
        self,
        messages: list[BaseMessage],
        tools: list | None = None,
        tool_choice: str | dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> ChatResult:
        """Send a chat request, optionally with tool calling."""
        llm = self._prepare_llm(tools, tool_choice)
        response: AIMessage = await llm.ainvoke(messages, temperature=temperature, max_tokens=max_tokens)
        return ChatResult(
            content=response.content if response.content else "",
            tool_calls=_extract_tool_calls(response),
            message=response,
        )

    async def chat_structured(
        self,
        messages: list[BaseMessage],
        schema: type[T],
        tools: list | None = None,
        tool_choice: str | dict | None = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> StructuredChatResult[T]:
        """Send a chat request constrained to a Pydantic schema, optionally with tools."""
        if tools:
            llm = self._prepare_llm(tools, tool_choice, response_format=schema)
            response: AIMessage = await llm.ainvoke(messages, temperature=temperature, max_tokens=max_tokens)
            tc = _extract_tool_calls(response)
            if tc:
                return StructuredChatResult(data=None, tool_calls=tc, message=response)
            parsed = schema.model_validate_json(response.content)
            return StructuredChatResult(data=parsed, tool_calls=[], message=response)

        structured_llm = self.llm.with_structured_output(schema)
        data = await structured_llm.ainvoke(messages, temperature=temperature, max_tokens=max_tokens)
        return StructuredChatResult(data=data, tool_calls=[], message=AIMessage(content=""))

    async def stream(
        self,
        messages: list[BaseMessage],
        tools: list | None = None,
        tool_choice: str | dict | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> AsyncIterator[AIMessageChunk]:
        """Stream chat response as an async iterator of message chunks."""
        llm = self._prepare_llm(tools, tool_choice)
        async for chunk in llm.astream(messages, temperature=temperature, max_tokens=max_tokens):
            yield chunk
