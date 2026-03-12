"""Integration tests for registration and invitation code flows."""

from datetime import datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import InvitationCode
from common.resp import Code
from conf import config as config_module
from conf.redis import get_redis


def _initiate(client: TestClient, email: str, password: str, invitation_code: str | None = None):
    """Post to /auth/register (initiate step only)."""
    body: dict = {"email": email, "password": password}
    if invitation_code is not None:
        body["invitation_code"] = invitation_code
    return client.post("/api/v1/auth/register", json=body)


class TestAuthRegister:
    """Tests for the two-step registration flow."""

    def test_register_initiate_success(self, client: TestClient):
        response = _initiate(client, "test@example.com", "Secret12")
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == Code.OK
        assert "Verification code sent" in body["message"]

    def test_register_verify_success(self, client: TestClient, register_and_verify):
        body = register_and_verify("newuser@example.com", "Secret12")
        assert body["code"] == Code.OK
        data = body["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client: TestClient, register_and_verify):
        register_and_verify("duplicate@example.com", "Pass1234")
        response = _initiate(client, "duplicate@example.com", "different")
        assert response.json()["code"] == Code.CONFLICT

    def test_register_sends_verification_email(self, client: TestClient, mock_email: list):
        _initiate(client, "emailtest@example.com", "Pass1234")
        assert len(mock_email) == 1
        assert mock_email[0]["email"] == "emailtest@example.com"
        assert mock_email[0]["purpose"] == "register"
        assert len(mock_email[0]["code"]) == 6

    def test_register_wrong_code_fails(self, client: TestClient):
        _initiate(client, "wrongcode@example.com", "Pass1234")
        response = client.post(
            "/api/v1/auth/register/verify",
            json={"email": "wrongcode@example.com", "code": "000000", "password": "Pass1234"},
        )
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_register_code_consumed_after_use(self, client: TestClient, register_and_verify):
        register_and_verify("consumed@example.com", "Pass1234")
        key = "verification:consumed@example.com:register"
        assert get_redis().get(key) is None


class TestInvitationDisabled:
    """Tests when require_invitation_code=False (default)."""

    def test_register_without_code_succeeds(self, client: TestClient):
        response = _initiate(client, "nocode@example.com", "Pass1234")
        assert response.json()["code"] == Code.OK

    def test_register_with_code_succeeds(self, client: TestClient):
        response = _initiate(client, "withcode@example.com", "Pass1234", "ANYCODE")
        assert response.json()["code"] == Code.OK


class TestInvitationRequired:
    """Tests when require_invitation_code=True."""

    def test_register_without_code_fails(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)
        response = _initiate(client, "nocode@example.com", "Pass1234")
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_register_with_invalid_code_fails(self, client: TestClient, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)
        response = _initiate(client, "bad@example.com", "Pass1234", "INVALID")
        assert response.json()["code"] == Code.BAD_REQUEST

    async def test_register_with_valid_code_full_flow(self, client: TestClient, session: AsyncSession, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="TESTCODE", max_uses=10, used_count=0, is_active=True)
        session.add(inv)
        await session.commit()
        await session.refresh(inv)

        # Step 1: Initiate
        response = _initiate(client, "valid@example.com", "Pass1234", "TESTCODE")
        assert response.json()["code"] == Code.OK

        # Step 2: Verify
        code = get_redis().get("verification:valid@example.com:register")
        verify_resp = client.post(
            "/api/v1/auth/register/verify",
            json={"email": "valid@example.com", "code": code, "password": "Pass1234"},
        )
        assert verify_resp.json()["code"] == Code.OK
        assert "access_token" in verify_resp.json()["data"]

        # Verify used_count incremented
        await session.refresh(inv)
        assert inv.used_count == 1

    async def test_register_with_exhausted_code_fails(self, client: TestClient, session: AsyncSession, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="MAXED", max_uses=1, used_count=1, is_active=True)
        session.add(inv)
        await session.commit()

        response = _initiate(client, "maxed@example.com", "Pass1234", "MAXED")
        assert response.json()["code"] == Code.BAD_REQUEST

    async def test_register_with_inactive_code_fails(self, client: TestClient, session: AsyncSession, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="INACTIVE", max_uses=0, used_count=0, is_active=False)
        session.add(inv)
        await session.commit()

        response = _initiate(client, "inactive@example.com", "Pass1234", "INACTIVE")
        assert response.json()["code"] == Code.BAD_REQUEST

    async def test_register_with_expired_code_fails(self, client: TestClient, session: AsyncSession, monkeypatch):
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(
            code="EXPIRED",
            max_uses=10,
            used_count=0,
            is_active=True,
            expires_at=datetime.now() - timedelta(days=1),
        )
        session.add(inv)
        await session.commit()

        response = _initiate(client, "expired@example.com", "Pass1234", "EXPIRED")
        assert response.json()["code"] == Code.BAD_REQUEST

    async def test_unlimited_invitation_code(self, client: TestClient, session: AsyncSession, monkeypatch):
        """Invitation code with max_uses=0 allows unlimited registrations."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="NOLIMIT", max_uses=0, used_count=100, is_active=True)
        session.add(inv)
        await session.commit()

        response = _initiate(client, "unlim@example.com", "Pass1234", "NOLIMIT")
        assert response.json()["code"] == Code.OK


class TestInvitationFullFlow:
    """Full end-to-end flows simulating frontend interaction with invitation codes."""

    async def test_invitation_register_then_login(
        self, client: TestClient, session: AsyncSession, monkeypatch, register_and_verify
    ):
        """Complete flow: initiate with invitation -> verify email -> login."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="FLOW", max_uses=10, used_count=0, is_active=True)
        session.add(inv)
        await session.commit()

        body = register_and_verify("flow@example.com", "Pass1234", "FLOW")
        assert body["code"] == Code.OK
        assert "access_token" in body["data"]

        # Login with the registered account
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "flow@example.com", "password": "Pass1234"},
        )
        assert login_resp.json()["code"] == Code.OK
        assert "access_token" in login_resp.json()["data"]

    async def test_invitation_register_then_access_profile(
        self, client: TestClient, session: AsyncSession, monkeypatch, register_and_verify
    ):
        """Full flow: invitation register -> use token to access protected endpoint."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="PROFILE", max_uses=10, used_count=0, is_active=True)
        session.add(inv)
        await session.commit()

        body = register_and_verify("profile@example.com", "Pass1234", "PROFILE")
        token = body["data"]["access_token"]

        me_resp = client.get("/api/v1/user/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.json()["code"] == Code.OK
        assert me_resp.json()["data"]["email"] == "profile@example.com"

    async def test_multiple_users_share_invitation_code(
        self, client: TestClient, session: AsyncSession, monkeypatch, register_and_verify
    ):
        """Multiple users register with the same invitation code, used_count increments."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="SHARED", max_uses=5, used_count=0, is_active=True)
        session.add(inv)
        await session.commit()
        await session.refresh(inv)

        for i in range(3):
            body = register_and_verify(f"shared{i}@example.com", "Pass1234", "SHARED")
            assert body["code"] == Code.OK

        await session.refresh(inv)
        assert inv.used_count == 3

    async def test_invitation_code_exhausted_mid_flow(
        self, client: TestClient, session: AsyncSession, monkeypatch, register_and_verify
    ):
        """Code with max_uses=1 works for first user, rejects second."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="ONCE", max_uses=1, used_count=0, is_active=True)
        session.add(inv)
        await session.commit()

        body = register_and_verify("first@example.com", "Pass1234", "ONCE")
        assert body["code"] == Code.OK

        response = _initiate(client, "second@example.com", "Pass1234", "ONCE")
        assert response.json()["code"] == Code.BAD_REQUEST

    async def test_invitation_email_sent_with_correct_params(
        self, client: TestClient, session: AsyncSession, monkeypatch, mock_email: list
    ):
        """Verify email is sent with correct parameters during invitation registration."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="EMAILCHK", max_uses=10, used_count=0, is_active=True)
        session.add(inv)
        await session.commit()

        _initiate(client, "invemail@example.com", "Pass1234", "EMAILCHK")
        assert len(mock_email) == 1
        assert mock_email[0]["email"] == "invemail@example.com"
        assert mock_email[0]["purpose"] == "register"
        assert len(mock_email[0]["code"]) == 6
