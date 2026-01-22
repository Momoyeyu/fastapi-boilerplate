import time
from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Any, NoReturn

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from jwt import PyJWT, PyJWTError

from common import erri
from conf.config import settings
from user.model import User


@lru_cache(maxsize=1)
def _jwt() -> PyJWT:
    return PyJWT()


DEBUG_EXEMPT_PATHS = {
    "/docs",  # Swagger UI
    "/redoc",  # ReDoc
    "/openapi.json",  # OpenAPI schema
}

# 白名单路径，DEBUG 模式下包含 FastAPI 文档路径
EXEMPT_PATHS: set[str] = set()
_EXEMPT_ENDPOINT_ATTR = "__jwt_exempt__"
_ROUTES_FROZEN_ATTR = "__jwt_routes_frozen__"
_SETUP_ATTR = "__jwt_middleware_installed__"


def exempt[TFunc: Callable[..., Any]](fn: TFunc) -> TFunc:
    setattr(fn, _EXEMPT_ENDPOINT_ATTR, True)
    return fn


def _build_exempt_paths(app: FastAPI) -> set[str]:
    paths: set[str] = set()
    for route in list(app.router.routes):
        if not isinstance(route, APIRoute):
            continue
        if getattr(route.endpoint, _EXEMPT_ENDPOINT_ATTR, False):
            paths.add(route.path)
    return paths


def _freeze_route_registration(app: FastAPI) -> None:
    if getattr(app, _ROUTES_FROZEN_ATTR, False):
        return

    setattr(app, _ROUTES_FROZEN_ATTR, True)

    def _blocked(*_: object, **__: object) -> NoReturn:
        raise RuntimeError("Routes are frozen. Register all routes before setup_jwt_middleware.")

    app.include_router = _blocked
    app.add_api_route = _blocked
    app.add_route = _blocked
    app.mount = _blocked
    app.router.include_router = _blocked
    app.router.add_api_route = _blocked


def create_token(user: User) -> str:
    now = int(time.time())
    payload = {"sub": user.username, "iat": now, "exp": now + settings.jwt_expire_seconds}
    return _jwt().encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> dict[str, Any]:
    try:
        decoded: dict[str, Any] = _jwt().decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return decoded
    except PyJWTError:
        raise erri.unauthorized("Invalid token") from None


def get_username(request: Request) -> str:
    state_user = getattr(request.state, "user", None)
    if isinstance(state_user, str) and state_user:
        return state_user

    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        payload = verify_token(token)
        sub = payload.get("sub")
        if isinstance(sub, str) and sub:
            return sub

    raise erri.unauthorized("Unauthorized")


def setup_jwt_middleware(app: FastAPI) -> None:
    if getattr(app, _SETUP_ATTR, False):
        return

    EXEMPT_PATHS.update(DEBUG_EXEMPT_PATHS if settings.debug else set())
    EXEMPT_PATHS.update(_build_exempt_paths(app))
    _freeze_route_registration(app)
    setattr(app, _SETUP_ATTR, True)

    @app.middleware("http")
    async def jwt_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path
        if path in EXEMPT_PATHS:
            return await call_next(request)

        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        token = auth.split(" ", 1)[1]
        try:
            payload = verify_token(token)
        except erri.BusinessError as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
        request.state.user = payload.get("sub")
        return await call_next(request)
