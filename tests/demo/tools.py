"""Simple tool registry for agent validation."""

from __future__ import annotations

import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def description(self) -> str: ...

    @property
    @abstractmethod
    def parameters(self) -> dict[str, Any]: ...

    @abstractmethod
    def execute(self, **kwargs: Any) -> str: ...

    def to_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def definitions(self) -> list[dict[str, Any]]:
        return [t.to_schema() for t in self._tools.values()]

    def execute(self, name: str, args: dict[str, Any]) -> str:
        tool = self._tools.get(name)
        if not tool:
            return f"Error: unknown tool '{name}'. Available: {', '.join(self._tools)}"
        try:
            return tool.execute(**args)
        except Exception as e:
            return f"Error executing {name}: {e}"


# ---------------------------------------------------------------------------
# Built-in tools
# ---------------------------------------------------------------------------


class ClockTool(Tool):
    name = "clock"
    description = "Get current date and time."
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class CalcTool(Tool):
    name = "calc"
    description = "Evaluate a Python math expression. Example: '2**10 + 3'."
    parameters = {
        "type": "object",
        "properties": {"expr": {"type": "string", "description": "Python math expression"}},
        "required": ["expr"],
    }

    def execute(self, expr: str = "", **kwargs) -> str:
        allowed = set("0123456789+-*/.() %,einfabsrotundmiaxpwsqlg")
        if not all(c in allowed for c in expr.replace(" ", "")):
            return f"Error: unsafe expression '{expr}'"
        try:
            import math

            result = eval(expr, {"__builtins__": {}}, vars(math))
            return str(result)
        except Exception as e:
            return f"Error: {e}"


class ShellTool(Tool):
    name = "shell"
    description = "Run a shell command and return stdout/stderr. Use for file listing, git, etc."
    parameters = {
        "type": "object",
        "properties": {"command": {"type": "string", "description": "Shell command to execute"}},
        "required": ["command"],
    }

    def execute(self, command: str = "", **kwargs) -> str:
        try:
            r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
            out = (r.stdout + r.stderr).strip()
            if r.returncode != 0:
                out += f"\n(exit code {r.returncode})"
            return out[:3000] if out else "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: command timed out (15s)"


def default_registry() -> ToolRegistry:
    reg = ToolRegistry()
    reg.register(ClockTool())
    reg.register(CalcTool())
    reg.register(ShellTool())
    return reg


# ---------------------------------------------------------------------------
# LangChain @tool wrappers (for LangGraph / create_react_agent)
# ---------------------------------------------------------------------------


def as_langchain_tools() -> list:
    """Return built-in tools as LangChain @tool functions."""
    from langchain_core.tools import tool

    @tool
    def clock() -> str:
        """Get current date and time."""
        return ClockTool().execute()

    @tool
    def calc(expr: str) -> str:
        """Evaluate a Python math expression. Example: '2**10 + 3'."""
        return CalcTool().execute(expr=expr)

    @tool
    def shell(command: str) -> str:
        """Run a shell command and return stdout/stderr."""
        return ShellTool().execute(command=command)

    return [clock, calc, shell]
