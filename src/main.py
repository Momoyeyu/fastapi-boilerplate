from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from loguru import logger

from auth.handler import router as auth_router
from common.resp import Response, ok
from common.trap import setup_exception_handlers
from conf import logging
from conf.db import close_db
from conf.openapi import setup_openapi
from conf.redis import close_redis
from middleware.auth import setup_auth_middleware
from middleware.logging import setup_logging_middleware
from tenant.handler import router as tenant_router
from user.handler import router as user_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Application started")
    yield
    logger.info("Application shutdown")
    close_redis()
    await close_db()


def init_routers(_app: FastAPI) -> None:
    api_router = APIRouter(prefix="/api/v1")

    @api_router.get("/")
    async def root() -> Response:
        return ok(message="Hello FastAPI + UV!")

    api_router.include_router(auth_router)
    api_router.include_router(user_router)
    api_router.include_router(tenant_router)
    _app.include_router(api_router)


def init_middlewares(_app: FastAPI) -> None:
    # Note: FastAPI middlewares execute in reverse order (last registered = first executed)
    # Order: logging -> auth -> handler
    setup_auth_middleware(_app)
    setup_logging_middleware(_app)


def create_app() -> FastAPI:
    logging.must_init()

    _app = FastAPI(
        title="FastAPI + UV Project",
        description="A FastAPI boilerplate initialized by UV",
        version="1.0.0",
        lifespan=lifespan,
    )

    init_routers(_app)
    init_middlewares(_app)
    setup_exception_handlers(_app)

    # Swagger Documents
    setup_openapi(_app)

    return _app


app = create_app()
