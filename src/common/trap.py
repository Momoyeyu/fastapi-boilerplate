"""Global exception handlers that convert exceptions to standardized resp.Response format.

Catches BusinessError (and other exceptions) and returns HTTP 200 with business error codes,
so handlers only need to return their DTO on success and raise BusinessError on failure.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger

from common import resp
from common.erri import BusinessError

STATUS_TO_BUSINESS_CODE: dict[int, int] = {
    400: resp.Code.BAD_REQUEST,
    401: resp.Code.UNAUTHORIZED,
    403: resp.Code.FORBIDDEN,
    404: resp.Code.NOT_FOUND,
    409: resp.Code.CONFLICT,
    422: resp.Code.INVALID_PARAM,
    429: resp.Code.RATE_LIMITED,
    500: resp.Code.INTERNAL_ERROR,
}


async def business_error_handler(_request: Request, exc: BusinessError) -> JSONResponse:
    code = STATUS_TO_BUSINESS_CODE.get(exc.status_code, resp.Code.INTERNAL_ERROR)
    return JSONResponse(
        status_code=200,
        content=resp.error(code, exc.detail).model_dump(),
    )


async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    code = STATUS_TO_BUSINESS_CODE.get(exc.status_code, resp.Code.INTERNAL_ERROR)
    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
    return JSONResponse(
        status_code=200,
        content=resp.error(code, detail).model_dump(),
    )


async def validation_error_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=200,
        content=resp.error(resp.Code.INVALID_PARAM, "Validation failed", data=exc.errors()).model_dump(),
    )


async def generic_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: {}", exc)
    return JSONResponse(
        status_code=200,
        content=resp.internal_error("Internal server error").model_dump(),
    )


def setup_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(BusinessError, business_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(HTTPException, http_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, generic_error_handler)  # type: ignore[arg-type]
