from contextlib import asynccontextmanager

from fastapi import FastAPI

from conf.db import close_db, init_db
from middleware.auth import setup_jwt_middleware
from user.handler import router as user_router

@asynccontextmanager
async def lifespan(application: FastAPI):
    init_db()
    yield
    close_db()

app = FastAPI(
    title="FastAPI + UV Project",
    description="A FastAPI demo initialized by UV",
    version="1.0.0",
    lifespan=lifespan,
)

setup_jwt_middleware(app)

app.include_router(user_router)

@app.get("/")
async def root():
    return {"message": "Hello FastAPI + UV!"}
