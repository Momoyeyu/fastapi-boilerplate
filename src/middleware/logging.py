"""Request/Response logging middleware for debugging."""

import json
import time
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI
from loguru import logger
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from conf.config import settings

# Paths to exclude from logging (e.g., health checks, static files)
_EXCLUDE_PATHS: set[str] = {
    "/docs",
    "/redoc",
    "/openapi.json",
    "/docs/oauth2-redirect",
}

# Headers to mask for security
_SENSITIVE_HEADERS: set[str] = {
    "authorization",
    "cookie",
    "x-api-key",
}

# Fields to mask in request body and query params
_SENSITIVE_FIELDS: set[str] = {
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "credential",
}


def _mask_headers(headers: dict[str, str]) -> dict[str, str]:
    """Mask sensitive header values."""
    return {k: "***" if k.lower() in _SENSITIVE_HEADERS else v for k, v in headers.items()}


def _mask_fields(data: Any) -> Any:
    """Recursively mask sensitive fields in dict/list."""
    if isinstance(data, dict):
        return {k: "***" if k.lower() in _SENSITIVE_FIELDS else _mask_fields(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_mask_fields(item) for item in data]
    return data


def _parse_body(body: bytes, content_type: str) -> Any:
    """Parse body based on content type, return parsed data or truncated string."""
    if not body:
        return None
    try:
        if "application/json" in content_type:
            return json.loads(body.decode("utf-8"))
        if "application/x-www-form-urlencoded" in content_type:
            parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
            return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}
    except (json.JSONDecodeError, UnicodeDecodeError):
        pass
    # Fallback: truncated string
    text = body.decode("utf-8", errors="replace")
    return f"{text[:500]}..." if len(text) > 500 else text


def _flatten_qs(qs: str) -> dict[str, Any]:
    """Parse and flatten query string."""
    parsed = parse_qs(qs, keep_blank_values=True)
    return {k: v[0] if len(v) == 1 else v for k, v in parsed.items()}


class LoggingMiddleware:
    """ASGI middleware that logs request and response details."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    def _prepare_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Apply header masking if not in debug mode."""
        return headers if settings.debug else _mask_headers(headers)

    def _prepare_data(self, data: Any) -> Any:
        """Apply field masking if not in debug mode."""
        return data if settings.debug else _mask_fields(data)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if path in _EXCLUDE_PATHS:
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        request_id = f"{int(time.time() * 1000)}"
        method = scope.get("method", "")

        # Capture request body
        request_body = b""
        body_consumed = False

        async def receive_wrapper() -> Message:
            nonlocal request_body, body_consumed
            message = await receive()
            if message["type"] == "http.request" and not body_consumed:
                request_body += message.get("body", b"")
                if not message.get("more_body", False):
                    body_consumed = True
            return message

        # Parse request headers
        headers = dict(scope.get("headers", []))
        headers_str = {k.decode(): v.decode() for k, v in headers.items()}
        content_type = headers_str.get("content-type", "")

        # Log request info
        logger.info(
            "Request {request_id} | {method} {path}",
            request_id=request_id,
            method=method,
            path=path,
        )
        logger.debug(
            "Request {request_id} headers: {headers}",
            request_id=request_id,
            headers=json.dumps(self._prepare_headers(headers_str), ensure_ascii=False),
        )

        # Log query params
        query_string = scope.get("query_string", b"").decode()
        if query_string:
            params = _flatten_qs(query_string)
            logger.debug(
                "Request {request_id} params: {params}",
                request_id=request_id,
                params=json.dumps(self._prepare_data(params), ensure_ascii=False),
            )

        # Capture response
        response_status = 0
        response_body = b""
        response_headers: list[tuple[bytes, bytes]] = []

        async def send_wrapper(message: Message) -> None:
            nonlocal response_status, response_body, response_headers
            if message["type"] == "http.response.start":
                response_status = message.get("status", 0)
                response_headers = list(message.get("headers", []))
            elif message["type"] == "http.response.body":
                response_body += message.get("body", b"")
            await send(message)

        # Process request
        await self.app(scope, receive_wrapper, send_wrapper)

        # Log request body (after consumed)
        if request_body:
            parsed_body = _parse_body(request_body, content_type)
            logger.debug(
                "Request {request_id} body: {body}",
                request_id=request_id,
                body=json.dumps(self._prepare_data(parsed_body), ensure_ascii=False),
            )

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log response
        logger.info(
            "Response {request_id} | {status_code} | {duration:.2f}ms",
            request_id=request_id,
            status_code=response_status,
            duration=duration_ms,
        )
        if response_body:
            resp_content_type = ""
            for key, value in response_headers:
                if key.lower() == b"content-type":
                    resp_content_type = value.decode()
                    break
            parsed_resp = _parse_body(response_body, resp_content_type)
            logger.debug(
                "Response {request_id} body: {body}",
                request_id=request_id,
                body=json.dumps(self._prepare_data(parsed_resp), ensure_ascii=False),
            )


def setup_logging_middleware(app: FastAPI) -> None:
    """Set up the logging middleware."""
    app.add_middleware(LoggingMiddleware)
