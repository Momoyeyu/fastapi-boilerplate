import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from functools import cache
from typing import Any, NoReturn

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from jwt import PyJWT, PyJWTError

from common import erri
from conf.config import settings
from user.model import (
    User,
    create_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)


@cache
def _jwt() -> PyJWT:
    return PyJWT()


DEBUG_EXEMPT_PATHS = {
    "/docs",  # Swagger UI
    "/redoc",  # ReDoc
    "/openapi.json",  # OpenAPI schema
}

# 白名单路径，DEBUG 模式下包含 FastAPI 文档路径
EXEMPT_PATHS: set[str] = {"/"}  # Root path for health check
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


@dataclass
class TokenPair:
    """A pair of access and refresh tokens."""

    access_token: str
    refresh_token: str
    expires_in: int
    refresh_token_expires_in: int


def create_access_token(username: str) -> tuple[str, int]:
    """Create a JWT access token for the user.

    Returns:
        A tuple of (access_token, expires_in).
    """
    now = int(time.time())
    expires_in = settings.jwt_expire_seconds
    payload = {"sub": username, "iat": now, "exp": now + expires_in}
    token = _jwt().encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expires_in


def create_token(user: User) -> TokenPair:
    """Create access and refresh tokens for the user.

    Returns:
        A TokenPair containing access_token, refresh_token, and expiration info.
    """
    if user.id is None:
        raise erri.internal("User ID is required for token creation")

    access_token, expires_in = create_access_token(user.username)
    refresh_token_obj = create_refresh_token(user.id, user.username)

    return TokenPair(
        access_token=access_token,
        refresh_token=refresh_token_obj.token,
        expires_in=expires_in,
        refresh_token_expires_in=settings.refresh_token_expire_seconds,
    )


def verify_token(token: str) -> dict[str, Any]:
    try:
        decoded: dict[str, Any] = _jwt().decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return decoded
    except PyJWTError:
        raise erri.unauthorized("Invalid token") from None


def refresh_tokens(refresh_token: str) -> TokenPair:
    """Refresh the access token using a refresh token.

    Implements Token Rotation: the old refresh token is revoked and a new one is issued.
    Uses a database transaction to ensure atomicity.

    Returns:
        A new TokenPair with fresh access and refresh tokens.

    Raises:
        BusinessError: If the refresh token is invalid, expired, or revoked.
    """
    new_refresh_token = rotate_refresh_token(refresh_token)
    if not new_refresh_token:
        raise erri.unauthorized("Invalid or expired refresh token")

    access_token, expires_in = create_access_token(new_refresh_token.username)

    return TokenPair(
        access_token=access_token,
        refresh_token=new_refresh_token.token,
        expires_in=expires_in,
        refresh_token_expires_in=settings.refresh_token_expire_seconds,
    )


def revoke_token(refresh_token: str) -> bool:
    """Revoke a refresh token.

    Returns:
        True if the token was revoked, False if it was not found.
    """
    return revoke_refresh_token(refresh_token)


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


def setup_auth_middleware(app: FastAPI) -> None:
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
