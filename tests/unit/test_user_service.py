from unittest.mock import MagicMock

import pytest

from auth import password as auth_password
from common import erri
from common.resp import Code
from user import profile
from user.model import User


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Create a mock settings object with default test values."""
    mock = MagicMock()
    mock.password_salt = "salt"
    monkeypatch.setattr(auth_password, "settings", mock)
    return mock


def test_get_user_profile_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(profile, "get_user", lambda username: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        profile.get_user_profile("alice")
    assert exc.value.code == Code.NOT_FOUND


def test_get_user_profile_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", password="x")
    monkeypatch.setattr(profile, "get_user", lambda username: user, raising=True)
    result = profile.get_user_profile("alice")
    assert result.username == "alice"
    assert result.email == "alice@test.com"


def test_update_my_profile_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(profile, "update_user_profile", lambda *args, **kwargs: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        profile.update_my_profile("alice", nickname="Alice", avatar_url=None)
    assert exc.value.code == Code.NOT_FOUND


def test_update_my_profile_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", password="x", nickname="Alice")
    monkeypatch.setattr(profile, "update_user_profile", lambda *args, **kwargs: user, raising=True)
    result = profile.update_my_profile("alice", nickname="Alice", avatar_url=None)
    assert result.nickname == "Alice"


def test_change_password_user_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(profile, "get_user", lambda username: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        profile.change_password("alice", "old", "new")
    assert exc.value.code == Code.NOT_FOUND


def test_change_password_wrong_old_password(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=1, username="alice", email="alice@test.com", password=auth_password.get_password_hash("correct"))
    monkeypatch.setattr(profile, "get_user", lambda username: user, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        profile.change_password("alice", "wrong", "new")
    assert exc.value.code == Code.BAD_REQUEST


def test_change_password_success(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=1, username="alice", email="alice@test.com", password=auth_password.get_password_hash("old"))
    monkeypatch.setattr(profile, "get_user", lambda username: user, raising=True)
    monkeypatch.setattr(profile, "update_user_password", lambda *args, **kwargs: True, raising=True)
    result = profile.change_password("alice", "old", "new")
    assert result is True
