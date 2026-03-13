"""Unit tests for common.llm module."""

import json

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from pydantic import BaseModel

from common.llm import ChatResult, LLMClient, StructuredChatResult, ToolCall, _extract_tool_calls

# ---------------------------------------------------------------------------
# Mock LLM
# ---------------------------------------------------------------------------


class FakeLLM:
    """Minimal mock that behaves like a BaseChatModel for testing."""

    def __init__(self, content="", tool_calls=None):
        self._content = content
        self._tool_calls = tool_calls or []

    async def ainvoke(self, messages, **kwargs):
        return AIMessage(content=self._content, tool_calls=self._tool_calls)

    async def astream(self, messages, **kwargs):
        yield AIMessageChunk(content=self._content)

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema):
        fake = self

        class _Wrapper:
            async def ainvoke(self_, messages, **kwargs):
                return schema.model_validate_json(fake._content)

        return _Wrapper()


# ---------------------------------------------------------------------------
# _extract_tool_calls
# ---------------------------------------------------------------------------


class TestExtractToolCalls:
    def test_empty(self):
        msg = AIMessage(content="hello")
        assert _extract_tool_calls(msg) == []

    def test_single_call(self):
        msg = AIMessage(
            content="",
            tool_calls=[{"id": "c1", "name": "get_weather", "args": {"city": "SF"}}],
        )
        result = _extract_tool_calls(msg)
        assert len(result) == 1
        assert result[0] == ToolCall(id="c1", name="get_weather", args={"city": "SF"})

    def test_multiple_calls(self):
        msg = AIMessage(
            content="",
            tool_calls=[
                {"id": "c1", "name": "tool_a", "args": {}},
                {"id": "c2", "name": "tool_b", "args": {"x": 1}},
            ],
        )
        assert len(_extract_tool_calls(msg)) == 2


# ---------------------------------------------------------------------------
# LLMClient — init & properties
# ---------------------------------------------------------------------------


class TestLLMClientInit:
    def test_custom_llm(self):
        fake = FakeLLM()
        client = LLMClient(llm=fake)
        assert client.llm is fake

    def test_model_property(self):
        fake = FakeLLM()
        client = LLMClient(llm=fake)
        assert client.model is fake

    def test_no_api_key_raises(self, monkeypatch):
        from common import llm as llm_module

        class FakeSettings:
            llm_api_key = type("S", (), {"get_secret_value": lambda self: ""})()
            llm_base_url = "http://test"
            llm_model_name = "test"

        monkeypatch.setattr(llm_module, "settings", FakeSettings())
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            LLMClient()


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------


class TestChat:
    async def test_text_response(self):
        client = LLMClient(llm=FakeLLM(content="Hello world"))
        result = await client.chat([HumanMessage(content="Hi")])
        assert isinstance(result, ChatResult)
        assert result.content == "Hello world"
        assert result.tool_calls == []
        assert isinstance(result.message, AIMessage)

    async def test_empty_content(self):
        client = LLMClient(llm=FakeLLM(content=""))
        result = await client.chat([HumanMessage(content="Hi")])
        assert result.content == ""

    async def test_with_tool_calls(self):
        tool_calls = [{"id": "c1", "name": "search", "args": {"q": "test"}}]
        client = LLMClient(llm=FakeLLM(content="", tool_calls=tool_calls))
        result = await client.chat(
            [HumanMessage(content="Search")],
            tools=[{"type": "function", "function": {"name": "search", "parameters": {}}}],
        )
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "search"
        assert result.tool_calls[0].args == {"q": "test"}
        assert result.tool_calls[0].id == "c1"

    async def test_message_is_aimessage(self):
        client = LLMClient(llm=FakeLLM(content="ok"))
        result = await client.chat([SystemMessage(content="sys"), HumanMessage(content="msg")])
        assert isinstance(result.message, AIMessage)


# ---------------------------------------------------------------------------
# chat_structured
# ---------------------------------------------------------------------------


class TestChatStructured:
    async def test_pydantic_model(self):
        class Movie(BaseModel):
            title: str
            year: int

        client = LLMClient(llm=FakeLLM(content=json.dumps({"title": "Inception", "year": 2010})))
        result = await client.chat_structured([HumanMessage(content="Tell me about Inception")], schema=Movie)
        assert isinstance(result, StructuredChatResult)
        assert isinstance(result.data, Movie)
        assert result.data.title == "Inception"
        assert result.data.year == 2010
        assert result.tool_calls == []

    async def test_with_tools_returns_tool_calls(self):
        class Output(BaseModel):
            answer: str

        tool_calls = [{"id": "c1", "name": "lookup", "args": {"key": "x"}}]
        client = LLMClient(llm=FakeLLM(content="", tool_calls=tool_calls))
        result = await client.chat_structured(
            [HumanMessage(content="Find x")],
            schema=Output,
            tools=[{"type": "function", "function": {"name": "lookup", "parameters": {}}}],
        )
        assert result.data is None
        assert len(result.tool_calls) == 1
        assert result.tool_calls[0].name == "lookup"

    async def test_with_tools_returns_data(self):
        class Output(BaseModel):
            answer: str

        client = LLMClient(llm=FakeLLM(content=json.dumps({"answer": "42"})))
        result = await client.chat_structured(
            [HumanMessage(content="What is the answer?")],
            schema=Output,
            tools=[{"type": "function", "function": {"name": "calc", "parameters": {}}}],
        )
        assert result.data is not None
        assert result.data.answer == "42"
        assert result.tool_calls == []


# ---------------------------------------------------------------------------
# stream
# ---------------------------------------------------------------------------


class TestStream:
    async def test_yields_chunks(self):
        client = LLMClient(llm=FakeLLM(content="Hello"))
        chunks = []
        async for chunk in client.stream([HumanMessage(content="Hi")]):
            chunks.append(chunk)
        assert len(chunks) == 1
        assert isinstance(chunks[0], AIMessageChunk)
        assert chunks[0].content == "Hello"

    async def test_with_tools(self):
        client = LLMClient(llm=FakeLLM(content="response"))
        chunks = []
        async for chunk in client.stream(
            [HumanMessage(content="Hi")],
            tools=[{"type": "function", "function": {"name": "t", "parameters": {}}}],
        ):
            chunks.append(chunk)
        assert len(chunks) >= 1


# ---------------------------------------------------------------------------
# create_chat_model
# ---------------------------------------------------------------------------


class TestCreateChatModel:
    def test_no_api_key_raises(self, monkeypatch):
        from common import llm as llm_module

        class FakeSettings:
            llm_api_key = type("S", (), {"get_secret_value": lambda self: ""})()
            llm_base_url = "http://test"
            llm_model_name = "test"

        monkeypatch.setattr(llm_module, "settings", FakeSettings())
        with pytest.raises(ValueError, match="LLM_API_KEY"):
            from common.llm import create_chat_model

            create_chat_model()
