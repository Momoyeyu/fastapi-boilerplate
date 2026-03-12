import pytest

from auth import service
from auth.dto import TokenPair
from common import erri
from common.resp import Code
from common.utils import get_password_hash
from user.model import User


def async_return(value):
    """Create an async function that returns the given value."""

    async def _inner(*args, **kwargs):
        return value

    return _inner


async def test_login_user_user_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user_by_identifier", async_return(None), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.login_user("alice", "pw")
    assert exc.value.code == Code.UNAUTHORIZED


async def test_login_user_password_mismatch(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", hashed_password=get_password_hash("correct"))
    monkeypatch.setattr(service, "get_user_by_identifier", async_return(user), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.login_user("alice", "wrong")
    assert exc.value.code == Code.UNAUTHORIZED


async def test_login_user_user_without_id(monkeypatch: pytest.MonkeyPatch):
    user = User(id=None, username="alice", email="alice@test.com", hashed_password=get_password_hash("pw"))
    monkeypatch.setattr(service, "get_user_by_identifier", async_return(user), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.login_user("alice", "pw")
    assert exc.value.code == Code.UNAUTHORIZED


async def test_login_user_success_creates_token(monkeypatch: pytest.MonkeyPatch):
    user = User(id=7, username="alice", email="alice@test.com", hashed_password=get_password_hash("pw"))
    monkeypatch.setattr(service, "get_user_by_identifier", async_return(user), raising=True)

    captured: dict[str, object] = {}
    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )

    def _create_token(passed_user: object):
        captured["user"] = passed_user
        return mock_token_pair

    monkeypatch.setattr(service, "create_token", _create_token, raising=True)

    token_pair = await service.login_user("alice", "pw")
    assert token_pair.access_token == "token-123"
    assert token_pair.refresh_token == "refresh-456"
    assert captured["user"] is user


async def test_login_user_with_email(monkeypatch: pytest.MonkeyPatch):
    user = User(id=7, username="alice", email="alice@test.com", hashed_password=get_password_hash("pw"))
    monkeypatch.setattr(service, "get_user_by_identifier", async_return(user), raising=True)

    mock_token_pair = TokenPair(
        access_token="token-123",
        refresh_token="refresh-456",
        expires_in=3600,
        refresh_token_expires_in=604800,
    )
    monkeypatch.setattr(service, "create_token", lambda u: mock_token_pair, raising=True)

    token_pair = await service.login_user("alice@test.com", "pw")
    assert token_pair.access_token == "token-123"
