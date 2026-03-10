"""Integration tests for invitation code registration flow."""

from datetime import datetime, timedelta

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


def _register_and_verify(client: TestClient, email: str, password: str, invitation_code: str | None = None) -> dict:
    """Complete two-step registration with optional invitation code."""
    _register(client, email, password, invitation_code)
    key = f"verification:{email.lower()}:register"
    code = get_redis().get(key)
    response = client.post(
        "/auth/register/verify",
        json={"email": email, "code": code, "password": password},
    )
    return response.json()


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

    def test_register_with_expired_code_fails(self, client: TestClient, session: Session, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(
            code="EXPIRED",
            max_uses=10,
            used_count=0,
            is_active=True,
            expires_at=datetime.now() - timedelta(days=1),
        )
        session.add(inv)
        session.commit()

        response = _register(client, "expired@example.com", "pass123", "EXPIRED")
        assert response.status_code == 200
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_unlimited_invitation_code(self, client: TestClient, session: Session, monkeypatch):
        """Invitation code with max_uses=0 allows unlimited registrations."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="NOLIMIT", max_uses=0, used_count=100, is_active=True)
        session.add(inv)
        session.commit()

        response = _register(client, "unlim@example.com", "pass123", "NOLIMIT")
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK


class TestInvitationFullFlow:
    """Full end-to-end flows simulating frontend interaction with invitation codes."""

    def test_invitation_register_then_login(self, client: TestClient, session: Session, monkeypatch):
        """Complete flow: initiate with invitation → verify email → login."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="FLOW", max_uses=10, used_count=0, is_active=True)
        session.add(inv)
        session.commit()

        body = _register_and_verify(client, "flow@example.com", "pass123", "FLOW")
        assert body["code"] == Code.OK
        assert "access_token" in body["data"]

        # Login with the registered account
        login_resp = client.post(
            "/auth/login",
            data={"username": "flow@example.com", "password": "pass123"},
        )
        assert login_resp.json()["code"] == Code.OK
        assert "access_token" in login_resp.json()["data"]

    def test_invitation_register_then_access_profile(self, client: TestClient, session: Session, monkeypatch):
        """Full flow: invitation register → use token to access protected endpoint."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="PROFILE", max_uses=10, used_count=0, is_active=True)
        session.add(inv)
        session.commit()

        body = _register_and_verify(client, "profile@example.com", "pass123", "PROFILE")
        token = body["data"]["access_token"]

        # Access protected profile endpoint
        me_resp = client.get("/user/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.json()["code"] == Code.OK
        assert me_resp.json()["data"]["email"] == "profile@example.com"

    def test_multiple_users_share_invitation_code(self, client: TestClient, session: Session, monkeypatch):
        """Multiple users register with the same invitation code, used_count increments."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="SHARED", max_uses=5, used_count=0, is_active=True)
        session.add(inv)
        session.commit()
        session.refresh(inv)

        for i in range(3):
            email = f"shared{i}@example.com"
            body = _register_and_verify(client, email, "pass123", "SHARED")
            assert body["code"] == Code.OK

        session.refresh(inv)
        assert inv.used_count == 3

    def test_invitation_code_exhausted_mid_flow(self, client: TestClient, session: Session, monkeypatch):
        """Code with max_uses=1 works for first user, rejects second."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="ONCE", max_uses=1, used_count=0, is_active=True)
        session.add(inv)
        session.commit()

        # First user succeeds
        body = _register_and_verify(client, "first@example.com", "pass123", "ONCE")
        assert body["code"] == Code.OK

        # Second user rejected at initiation
        response = _register(client, "second@example.com", "pass123", "ONCE")
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_invitation_email_sent_with_correct_params(
        self, client: TestClient, session: Session, monkeypatch, mock_email: list
    ):
        """Verify email is sent with correct parameters during invitation registration."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="EMAILCHK", max_uses=10, used_count=0, is_active=True)
        session.add(inv)
        session.commit()

        _register(client, "invemail@example.com", "pass123", "EMAILCHK")
        assert len(mock_email) == 1
        assert mock_email[0]["email"] == "invemail@example.com"
        assert mock_email[0]["purpose"] == "register"
        assert len(mock_email[0]["code"]) == 6
