"""Standardized API response format with business error codes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class Code:
    """Business error codes, derived from HTTP status codes x 100."""

    OK = 0
    BAD_REQUEST = 40000
    UNAUTHORIZED = 40100
    FORBIDDEN = 40300
    NOT_FOUND = 40400
    CONFLICT = 40900
    INVALID_PARAM = 42200
    RATE_LIMITED = 42900
    INTERNAL_ERROR = 50000


class Response(BaseModel):
    """Unified API response envelope."""

    code: int = Code.OK
    message: str = "ok"
    data: Any = None


def ok(data: Any = None, message: str = "ok") -> Response:
    return Response(code=Code.OK, message=message, data=data)


def error(code: int, message: str, data: Any = None) -> Response:
    return Response(code=code, message=message, data=data)
