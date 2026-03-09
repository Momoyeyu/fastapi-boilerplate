"""Integration tests for invitation code registration flow."""

from fastapi.testclient import TestClient
from sqlmodel import Session

from common.resp import Code
from conf import config as config_module
from conf.redis import get_redis
from invitation.model import InvitationCode


def _register(client: TestClient, email: str, password: str, invitation_code: str | None = None):
    body: dict = {"email": email, "password": password}
    if invitation_code is not None:
        body["invitation_code"] = invitation_code
    return client.post("/auth/register", json=body)


class TestInvitationDisabled:
    """Tests when require_invitation_code=False (default)."""

    def test_register_without_code_succeeds(self, client: TestClient):
        response = _register(client, "nocode@example.com", "pass123")
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

    def test_register_with_code_succeeds(self, client: TestClient):
        response = _register(client, "withcode@example.com", "pass123", "ANYCODE")
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK


class TestInvitationRequired:
    """Tests when require_invitation_code=True."""

    def test_register_without_code_fails(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)
        response = _register(client, "nocode@example.com", "pass123")
        assert response.status_code == 200
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_register_with_invalid_code_fails(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)
        response = _register(client, "bad@example.com", "pass123", "INVALID")
        assert response.status_code == 200
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_register_with_valid_code_full_flow(self, client: TestClient, session: Session, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="TESTCODE", max_uses=10, used_count=0, is_active=True)
        session.add(inv)
        session.commit()
        session.refresh(inv)

        # Step 1: Initiate
        response = _register(client, "valid@example.com", "pass123", "TESTCODE")
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

        # Step 2: Verify
        key = "verification:valid@example.com:register"
        code = get_redis().get(key)
        verify_resp = client.post(
            "/auth/register/verify",
            json={"email": "valid@example.com", "code": code, "password": "pass123"},
        )
        assert verify_resp.status_code == 200
        assert verify_resp.json()["code"] == Code.OK
        assert "access_token" in verify_resp.json()["data"]

        # Verify used_count incremented
        session.refresh(inv)
        assert inv.used_count == 1

    def test_register_with_exhausted_code_fails(self, client: TestClient, session: Session, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="MAXED", max_uses=1, used_count=1, is_active=True)
        session.add(inv)
        session.commit()

        response = _register(client, "maxed@example.com", "pass123", "MAXED")
        assert response.status_code == 200
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_register_with_inactive_code_fails(self, client: TestClient, session: Session, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="INACTIVE", max_uses=0, used_count=0, is_active=False)
        session.add(inv)
        session.commit()

        response = _register(client, "inactive@example.com", "pass123", "INACTIVE")
        assert response.status_code == 200
        assert response.json()["code"] == Code.BAD_REQUEST
