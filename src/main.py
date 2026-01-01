from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI

from conf.db import close_db, init_db
from middleware.auth import setup_jwt_middleware
from user.handler import router as user_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield
    close_db()


def init_routers(_app: FastAPI) -> None:
    root_router = APIRouter()

    @root_router.get("/")
    async def root():
        return {"message": "Hello FastAPI + UV!"}

    _app.include_router(root_router)
    _app.include_router(user_router)


def init_middlewares(_app: FastAPI) -> None:
    setup_jwt_middleware(_app)


def create_app() -> FastAPI:
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
