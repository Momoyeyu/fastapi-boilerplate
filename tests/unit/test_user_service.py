from unittest.mock import MagicMock

import pytest

from auth import service as auth_service
from common import erri
from user import service
from user.model import User


@pytest.fixture
def mock_settings(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Create a mock settings object with default test values."""
    mock = MagicMock()
    mock.password_salt = "salt"
    monkeypatch.setattr(auth_service, "settings", mock)
    return mock


def test_get_user_profile_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", lambda username: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.get_user_profile("alice")
    assert exc.value.status_code == 404


def test_get_user_profile_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", password="x")
    monkeypatch.setattr(service, "get_user", lambda username: user, raising=True)
    result = service.get_user_profile("alice")
    assert result.username == "alice"
    assert result.email == "alice@test.com"


def test_update_my_profile_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "update_user_profile", lambda *args, **kwargs: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.update_my_profile("alice", nickname="Alice", avatar_url=None)
    assert exc.value.status_code == 404


def test_update_my_profile_success(monkeypatch: pytest.MonkeyPatch):
    user = User(id=1, username="alice", email="alice@test.com", password="x", nickname="Alice")
    monkeypatch.setattr(service, "update_user_profile", lambda *args, **kwargs: user, raising=True)
    result = service.update_my_profile("alice", nickname="Alice", avatar_url=None)
    assert result.nickname == "Alice"


def test_change_password_user_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", lambda username: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.change_password("alice", "old", "new")
    assert exc.value.status_code == 404


def test_change_password_wrong_old_password(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=1, username="alice", email="alice@test.com", password=auth_service.get_password_hash("correct"))
    monkeypatch.setattr(service, "get_user", lambda username: user, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.change_password("alice", "wrong", "new")
    assert exc.value.status_code == 400


def test_change_password_success(monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock):
    user = User(id=1, username="alice", email="alice@test.com", password=auth_service.get_password_hash("old"))
    monkeypatch.setattr(service, "get_user", lambda username: user, raising=True)
    monkeypatch.setattr(service, "update_user_password", lambda *args, **kwargs: True, raising=True)
    result = service.change_password("alice", "old", "new")
    assert result is True
