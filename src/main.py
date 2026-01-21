from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI
from loguru import logger

from conf import logging
from conf.db import close_db, init_db
from middleware.auth import setup_jwt_middleware
from user.handler import router as user_router


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    init_db()
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
    _app.include_router(user_router)


def init_middlewares(_app: FastAPI) -> None:
    setup_jwt_middleware(_app)


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

    return _app


app = create_app()
