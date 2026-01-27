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


def test_register_user_when_user_exists(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", lambda username: User(id=1, username=username, password="x"), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.register_user("alice", "pw")
    assert exc.value.status_code == 409


def test_register_user_success_hashes_password_and_calls_create(
    monkeypatch: pytest.MonkeyPatch, mock_settings: MagicMock
):
    monkeypatch.setattr(service, "get_user", lambda username: None, raising=True)

    captured: dict[str, str] = {}

    def _create_user(username: str, password: str):
        captured["username"] = username
        captured["password"] = password
        return User(id=123, username=username, password=password)

    monkeypatch.setattr(service, "create_user", _create_user, raising=True)

    user = service.register_user("alice", "pw")
    assert user.id == 123
    assert user.username == "alice"
    assert captured["username"] == "alice"
    assert captured["password"] == auth_service.get_password_hash("pw")


def test_register_user_create_failed_returns_none(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", lambda username: None, raising=True)
    monkeypatch.setattr(service, "create_user", lambda username, password: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.register_user("alice", "pw")
    assert exc.value.status_code == 500


def test_register_user_create_failed_returns_user_without_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", lambda username: None, raising=True)
    monkeypatch.setattr(
        service,
        "create_user",
        lambda username, password: User(id=None, username=username, password=password),
        raising=True,
    )
    with pytest.raises(erri.BusinessError) as exc:
        service.register_user("alice", "pw")
    assert exc.value.status_code == 500
