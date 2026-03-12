import pytest

from common import erri
from common.resp import Code
from common.utils import get_password_hash
from user import service
from user.model import User


def async_return(value):
    """Create an async function that returns the given value."""

    async def _inner(*args, **kwargs):
        return value

    return _inner


async def test_get_user_profile_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", async_return(None), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.get_user_profile("alice")
    assert exc.value.code == Code.NOT_FOUND


async def test_get_user_profile_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", hashed_password="x")
    monkeypatch.setattr(service, "get_user", async_return(user), raising=True)
    result = await service.get_user_profile("alice")
    assert result.username == "alice"
    assert result.email == "alice@test.com"


async def test_update_my_profile_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "update_user_profile", async_return(None), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.update_my_profile("alice")
    assert exc.value.code == Code.NOT_FOUND


async def test_update_my_profile_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", hashed_password="x", avatar_url="http://img.png")
    monkeypatch.setattr(service, "update_user_profile", async_return(user), raising=True)
    result, token_pair = await service.update_my_profile("alice", avatar_url="http://img.png")
    assert result.avatar_url == "http://img.png"
    assert token_pair is None


async def test_change_password_user_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", async_return(None), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.change_password("alice", "old", "NewPass1")
    assert exc.value.code == Code.NOT_FOUND


async def test_change_password_wrong_old_password(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", hashed_password=get_password_hash("correct"))
    monkeypatch.setattr(service, "get_user", async_return(user), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await service.change_password("alice", "wrong", "NewPass1")
    assert exc.value.code == Code.BAD_REQUEST


async def test_change_password_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", hashed_password=get_password_hash("old"))
    monkeypatch.setattr(service, "get_user", async_return(user), raising=True)
    monkeypatch.setattr(service, "update_user_password", async_return(True), raising=True)

    monkeypatch.setattr(service, "revoke_all_for_user", lambda uid: 0)

    result = await service.change_password("alice", "old", "NewPass1")
    assert result is True
