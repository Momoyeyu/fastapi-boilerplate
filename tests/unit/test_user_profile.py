import pytest

from auth import password as auth_password
from common import erri
from common.resp import Code
from user import profile
from user.model import User


def async_return(value):
    """Create an async function that returns the given value."""

    async def _inner(*args, **kwargs):
        return value

    return _inner


async def test_get_user_profile_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(profile, "get_user", async_return(None), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await profile.get_user_profile("alice")
    assert exc.value.code == Code.NOT_FOUND


async def test_get_user_profile_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", hashed_password="x")
    monkeypatch.setattr(profile, "get_user", async_return(user), raising=True)
    result = await profile.get_user_profile("alice")
    assert result.username == "alice"
    assert result.email == "alice@test.com"


async def test_update_my_profile_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(profile, "update_user_profile", async_return(None), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await profile.update_my_profile("alice", avatar_url=None)
    assert exc.value.code == Code.NOT_FOUND


async def test_update_my_profile_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", hashed_password="x", avatar_url="http://img.png")
    monkeypatch.setattr(profile, "update_user_profile", async_return(user), raising=True)
    result = await profile.update_my_profile("alice", avatar_url="http://img.png")
    assert result.avatar_url == "http://img.png"


async def test_change_password_user_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(profile, "get_user", async_return(None), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await profile.change_password("alice", "old", "new")
    assert exc.value.code == Code.NOT_FOUND


async def test_change_password_wrong_old_password(monkeypatch: pytest.MonkeyPatch):
    user = User(
        id=1, username="alice", email="alice@test.com", hashed_password=auth_password.get_password_hash("correct")
    )
    monkeypatch.setattr(profile, "get_user", async_return(user), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        await profile.change_password("alice", "wrong", "new")
    assert exc.value.code == Code.BAD_REQUEST


async def test_change_password_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", hashed_password=auth_password.get_password_hash("old"))
    monkeypatch.setattr(profile, "get_user", async_return(user), raising=True)
    monkeypatch.setattr(profile, "update_user_password", async_return(True), raising=True)
    result = await profile.change_password("alice", "old", "new")
    assert result is True
