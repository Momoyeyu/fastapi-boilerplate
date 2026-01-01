import hashlib

import pytest

from common import erri
from user import service
from user.model import User


def test_get_password_hash_uses_salt(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "PASSWORD_SALT", "salt", raising=True)
    password = "pw"
    expected = hashlib.sha512((password + "salt").encode("utf-8")).hexdigest()
    assert service.get_password_hash(password) == expected


def test_register_user_when_user_exists(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", lambda username: User(id=1, username=username, password="x"), raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.register_user("alice", "pw")
    assert exc.value.status_code == 409


def test_register_user_success_hashes_password_and_calls_create(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "PASSWORD_SALT", "salt", raising=True)
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
    assert captured["password"] == service.get_password_hash("pw")


def test_register_user_create_failed_returns_none(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", lambda username: None, raising=True)
    monkeypatch.setattr(service, "create_user", lambda username, password: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.register_user("alice", "pw")
    assert exc.value.status_code == 500


def test_register_user_create_failed_returns_user_without_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", lambda username: None, raising=True)
    monkeypatch.setattr(
        service, "create_user", lambda username, password: User(id=None, username=username, password=password), raising=True
    )
    with pytest.raises(erri.BusinessError) as exc:
        service.register_user("alice", "pw")
    assert exc.value.status_code == 500


def test_login_user_user_not_found(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "get_user", lambda username: None, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.login_user("alice", "pw")
    assert exc.value.status_code == 401


def test_login_user_password_mismatch(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "PASSWORD_SALT", "salt", raising=True)
    user = User(id=1, username="alice", password=service.get_password_hash("correct"))
    monkeypatch.setattr(service, "get_user", lambda username: user, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.login_user("alice", "wrong")
    assert exc.value.status_code == 401


def test_login_user_user_without_id(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "PASSWORD_SALT", "salt", raising=True)
    user = User(id=None, username="alice", password=service.get_password_hash("pw"))
    monkeypatch.setattr(service, "get_user", lambda username: user, raising=True)
    with pytest.raises(erri.BusinessError) as exc:
        service.login_user("alice", "pw")
    assert exc.value.status_code == 401


def test_login_user_success_creates_token(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(service, "PASSWORD_SALT", "salt", raising=True)
    user = User(id=7, username="alice", password=service.get_password_hash("pw"))
    monkeypatch.setattr(service, "get_user", lambda username: user, raising=True)

    captured: dict[str, object] = {}

    def _create_token(passed_user: object):
        captured["user"] = passed_user
        return "token-123"

    monkeypatch.setattr(service.auth, "create_token", _create_token, raising=True)

    token = service.login_user("alice", "pw")
    assert token == "token-123"
    assert captured["user"] is user
