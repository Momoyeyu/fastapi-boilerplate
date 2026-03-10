"""Global exception handlers that convert exceptions to standardized resp.Response format.

Catches BusinessError (and other exceptions) and returns proper HTTP status codes
with business error codes in the response body. Handlers only need to return their
DTO on success and raise BusinessError on failure.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from common import resp
from common.erri import BusinessError

_STATUS_TO_BUSINESS_CODE: dict[int, int] = {
    400: resp.Code.BAD_REQUEST,
    401: resp.Code.UNAUTHORIZED,
    403: resp.Code.FORBIDDEN,
    404: resp.Code.NOT_FOUND,
    409: resp.Code.CONFLICT,
    422: resp.Code.INVALID_PARAM,
    429: resp.Code.RATE_LIMITED,
    500: resp.Code.INTERNAL_ERROR,
}


async def _handle_business_error(_request: Request, exc: BusinessError) -> JSONResponse:
    """BusinessError already carries code + status_code. Just format and return."""
    return JSONResponse(
        status_code=exc.status_code,
        content=resp.error(exc.code, exc.message).model_dump(),
    )


async def _handle_http_error(_request: Request, exc: HTTPException) -> JSONResponse:
    """FastAPI/Starlette HTTP exceptions (e.g. 422 from path params)."""
    code = _STATUS_TO_BUSINESS_CODE.get(exc.status_code, resp.Code.INTERNAL_ERROR)
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=resp.error(code, detail).model_dump(),
    )


async def _handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Pydantic request validation failures."""
    return JSONResponse(
        status_code=422,
        content=resp.error(resp.Code.INVALID_PARAM, "Validation failed", data=exc.errors()).model_dump(),
    )


async def _handle_generic_error(_request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log and return generic 500."""
    logger.exception("Unhandled exception: {}", exc)
    return JSONResponse(
        status_code=500,
        content=resp.error(resp.Code.INTERNAL_ERROR, "Internal server error").model_dump(),
    )


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BusinessError, _handle_business_error)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, _handle_http_error)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, _handle_validation_error)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, _handle_generic_error)  # type: ignore[arg-type]
