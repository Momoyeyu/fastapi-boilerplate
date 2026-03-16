import re
from collections.abc import Awaitable, Callable
from functools import cache
from typing import Any, NoReturn
from uuid import UUID

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from jwt import PyJWT, PyJWTError

from common import erri, resp
from conf.config import settings


@cache
def _jwt() -> PyJWT:
    return PyJWT()


DEBUG_EXEMPT_PATHS = {
    "/docs",  # Swagger UI
    "/redoc",  # ReDoc
    "/openapi.json",  # OpenAPI schema
}

EXEMPT_PATHS: set[str] = {"/api/v1", "/api/v1/"}  # Root path for health check
EXEMPT_PATTERNS: list[re.Pattern[str]] = []  # Regex patterns for parameterized exempt paths
_EXEMPT_ENDPOINT_ATTR = "__jwt_exempt__"
_ROUTES_FROZEN_ATTR = "__jwt_routes_frozen__"
_SETUP_ATTR = "__jwt_middleware_installed__"


def exempt[TFunc: Callable[..., Any]](fn: TFunc) -> TFunc:
    setattr(fn, _EXEMPT_ENDPOINT_ATTR, True)
    return fn


def _path_to_regex(path: str) -> re.Pattern[str]:
    """Convert a path template like /auth/{provider}/callback to a regex."""
    pattern = re.sub(r"\{[^}]+\}", r"[^/]+", path)
    return re.compile(f"^{pattern}$")


def _build_exempt_paths(app: FastAPI) -> set[str]:
    paths: set[str] = set()
    for route in list(app.router.routes):
        if not isinstance(route, APIRoute):
            continue
        if getattr(route.endpoint, _EXEMPT_ENDPOINT_ATTR, False):
            if "{" in route.path:
                EXEMPT_PATTERNS.append(_path_to_regex(route.path))
            else:
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


def verify_token(token: str) -> dict[str, Any]:
    """Verify a JWT token and return the payload."""
    try:
        decoded: dict[str, Any] = _jwt().decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return decoded
    except PyJWTError:
        raise erri.unauthorized("Invalid token") from None


def _decode_from_header(request: Request) -> dict[str, Any]:
    """Decode JWT from Authorization header. Fallback when middleware didn't run."""
    authorization = request.headers.get("Authorization")
    if authorization and authorization.startswith("Bearer "):
        token = authorization.split(" ", 1)[1]
        return verify_token(token)
    raise erri.unauthorized("Unauthorized")


def get_user_id(request: Request) -> UUID:
    """Get user_id from request state (set by middleware) or decode from header.

    JWT sub claim stores user_id (immutable UUID), so no DB lookup needed.
    """
    state_uid = getattr(request.state, "user_id", None)
    if isinstance(state_uid, UUID):
        return state_uid

    payload = _decode_from_header(request)
    sub = payload.get("sub")
    if isinstance(sub, str) and sub:
        return UUID(sub)
    raise erri.unauthorized("Unauthorized")


def get_username(request: Request) -> str:
    """Get username from request state (set by middleware) or decode from header."""
    state_username = getattr(request.state, "username", None)
    if isinstance(state_username, str) and state_username:
        return state_username

    payload = _decode_from_header(request)
    username = payload.get("username")
    if isinstance(username, str) and username:
        return username
    raise erri.unauthorized("Unauthorized")


async def get_tenant_id(request: Request) -> UUID | None:
    """Resolve the current tenant UUID from X-Tenant-ID header.

    Returns:
        tenant_id if header is present and user is a member, None otherwise.

    Raises:
        BusinessError: If the header value is invalid or user is not a member.
    """
    from tenant.model import get_user_tenant

    header_tenant = request.headers.get("X-Tenant-ID")
    if not header_tenant:
        return None

    try:
        tenant_id = UUID(header_tenant)
    except ValueError:
        raise erri.bad_request("Invalid X-Tenant-ID header") from None

    user_id = get_user_id(request)
    user_tenant = await get_user_tenant(user_id, tenant_id)
    if not user_tenant:
        raise erri.forbidden("Not a member of this tenant")
    return tenant_id


def setup_auth_middleware(app: FastAPI) -> None:
    """Setup JWT authentication middleware."""
    if getattr(app, _SETUP_ATTR, False):
        return

    EXEMPT_PATHS.update(DEBUG_EXEMPT_PATHS if settings.debug else set())
    EXEMPT_PATHS.update(_build_exempt_paths(app))
    _freeze_route_registration(app)
    setattr(app, _SETUP_ATTR, True)

    @app.middleware("http")
    async def jwt_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        path = request.url.path
        if path in EXEMPT_PATHS or any(p.match(path) for p in EXEMPT_PATTERNS):
            return await call_next(request)

        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content=resp.error(resp.Code.UNAUTHORIZED, "Unauthorized").model_dump(),
            )
        token = auth.split(" ", 1)[1]
        try:
            payload = verify_token(token)
        except erri.BusinessError as e:
            return JSONResponse(status_code=e.status_code, content=resp.error(e.code, e.message).model_dump())

        # Store both user_id and username in request state
        sub = payload.get("sub", "")
        try:
            request.state.user_id = UUID(sub) if sub else None
        except ValueError:
            return JSONResponse(
                status_code=401,
                content=resp.error(resp.Code.UNAUTHORIZED, "Invalid token").model_dump(),
            )
        request.state.username = payload.get("username", "")
        return await call_next(request)
