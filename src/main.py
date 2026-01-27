from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from loguru import logger

from auth.handler import router as auth_router
from conf import logging
from conf.db import close_db
from conf.openapi import setup_openapi
from middleware.auth import setup_auth_middleware
from middleware.logging import setup_logging_middleware
from user.handler import router as user_router
from user.service import ensure_admin_user


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    ensure_admin_user()
    logger.info("Application started")
    yield
    logger.info("Application shutdown")
    close_db()


def init_routers(_app: FastAPI) -> None:
    root_router = APIRouter()

    @root_router.get("/")
    async def root() -> dict[str, Any]:
        return {"message": "Hello FastAPI + UV!"}

    _app.include_router(root_router)
    _app.include_router(auth_router)
    _app.include_router(user_router)


def init_middlewares(_app: FastAPI) -> None:
    # Note: FastAPI middlewares execute in reverse order (last registered = first executed)
    # Order: logging -> auth -> handler
    setup_auth_middleware(_app)
    setup_logging_middleware(_app)


def create_app() -> FastAPI:
    logging.must_init()

    _app = FastAPI(
        title="FastAPI + UV Project",
        description="A FastAPI demo initialized by UV",
        version="1.0.0",
        lifespan=lifespan,
    )

    init_routers(_app)
    init_middlewares(_app)

    # Swagger Documents
    setup_openapi(_app)

    return _app


app = create_app()
