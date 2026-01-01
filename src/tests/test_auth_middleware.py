import pytest
from fastapi import APIRouter, FastAPI, Request
from fastapi.testclient import TestClient
from middleware import auth
from user import handler as user_handler
from user.model import User


def test_jwt_middleware_returns_401_when_missing_authorization_header():
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()

    @app.get("/protected")
    async def protected():
        return {"ok": True}

    auth.setup_jwt_middleware(app)
    client = TestClient(app)
    resp = client.get("/protected")
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Unauthorized"}


def test_jwt_middleware_returns_401_when_token_invalid():
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()

    @app.get("/protected")
    async def protected():
        return {"ok": True}

    auth.setup_jwt_middleware(app)
    client = TestClient(app)
    resp = client.get("/protected", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
    assert resp.json() == {"detail": "Invalid token"}


def test_jwt_middleware_allows_exempt_route_without_authorization_header():
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()

    @auth.exempt
    @app.get("/public")
    async def public():
        return {"ok": True}

    auth.setup_jwt_middleware(app)
    client = TestClient(app)
    resp = client.get("/public")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_jwt_middleware_allows_exempt_route_with_router_prefix():
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()

    router = APIRouter(prefix="/user")

    @auth.exempt
    @router.get("/ping")
    async def ping():
        return {"pong": True}

    app.include_router(router)
    auth.setup_jwt_middleware(app)
    client = TestClient(app)
    resp = client.get("/user/ping")
    assert resp.status_code == 200
    assert resp.json() == {"pong": True}


def test_setup_jwt_middleware_freezes_route_registration():
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()

    auth.setup_jwt_middleware(app)

    with pytest.raises(RuntimeError):
        @app.get("/late")
        async def late():
            return {"ok": True}


def test_user_login_returns_token_in_header(monkeypatch: pytest.MonkeyPatch):
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()
    app.include_router(user_handler.router)
    auth.setup_jwt_middleware(app)
    client = TestClient(app)

    monkeypatch.setattr(user_handler.service, "login_user", lambda username, password: "token-123", raising=True)

    resp = client.post("/user/login", json={"username": "alice", "password": "pw"})
    assert resp.status_code == 200
    assert resp.json() == {}
    assert resp.headers.get("x-jwt-token") == "token-123"


def test_get_username_returns_username_from_request_state_when_middleware_installed():
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()

    @app.get("/me")
    async def me(request: Request):
        return {"username": auth.get_username(request)}

    auth.setup_jwt_middleware(app)
    client = TestClient(app)

    token = auth.create_token(User(id=1, username="alice", password="x"))
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "alice"}


def test_get_username_can_parse_username_from_authorization_header_without_middleware():
    app = FastAPI()

    @app.get("/me")
    async def me(request: Request):
        return {"username": auth.get_username(request)}

    client = TestClient(app)

    token = auth.create_token(User(id=2, username="bob", password="x"))
    resp = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "bob"}


def test_user_whoami_returns_username_from_token():
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()
    app.include_router(user_handler.router)
    auth.setup_jwt_middleware(app)
    client = TestClient(app)

    token = auth.create_token(User(id=1, username="alice", password="x"))
    resp = client.get("/user/whoami", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == {"username": "alice"}


def test_user_me_uses_get_username_to_fetch_profile(monkeypatch: pytest.MonkeyPatch):
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()
    app.include_router(user_handler.router)
    auth.setup_jwt_middleware(app)
    client = TestClient(app)

    captured: dict[str, str] = {}

    def _get_user_profile(username: str) -> User:
        captured["username"] = username
        return User(
            id=1,
            username=username,
            password="x",
            nickname="Alice",
            email="alice@example.com",
            avatar_url="https://example.com/a.png",
            role="user",
            is_active=True,
        )

    monkeypatch.setattr(user_handler.service, "get_user_profile", _get_user_profile, raising=True)

    token = auth.create_token(User(id=1, username="alice", password="x"))
    resp = client.get("/user/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert captured["username"] == "alice"
    assert resp.json()["username"] == "alice"


def test_user_me_patch_updates_profile(monkeypatch: pytest.MonkeyPatch):
    auth.EXEMPT_PATHS.clear()
    app = FastAPI()
    app.include_router(user_handler.router)
    auth.setup_jwt_middleware(app)
    client = TestClient(app)

    def _update_my_profile(username: str, *, nickname: str | None, email: str | None, avatar_url: str | None) -> User:
        return User(
            id=1,
            username=username,
            password="x",
            nickname=nickname,
            email=email,
            avatar_url=avatar_url,
            role="user",
            is_active=True,
        )

    monkeypatch.setattr(user_handler.service, "update_my_profile", _update_my_profile, raising=True)

    token = auth.create_token(User(id=1, username="alice", password="x"))
    resp = client.patch(
        "/user/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"nickname": "NewName"},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == "alice"
    assert resp.json()["nickname"] == "NewName"
