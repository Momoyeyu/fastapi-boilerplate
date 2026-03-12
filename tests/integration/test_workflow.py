"""
End-to-end workflow tests simulating complete frontend user journeys.

Each test covers a realistic multi-step interaction that spans multiple
API modules, verifying that the system works correctly as a whole.
"""

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from auth.model import InvitationCode
from common.resp import Code
from conf import config as config_module
from conf.redis import get_redis


class TestNewUserOnboarding:
    """Simulate a new user's first experience from signup to profile setup."""

    def test_standard_onboarding(self, client: TestClient, mock_email: list):
        """Register -> verify email -> view profile -> update profile -> logout."""
        # 1. Initiate registration
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "onboard@example.com", "password": "Pass1234"},
        )
        assert resp.json()["code"] == Code.OK
        assert len(mock_email) == 1

        # 2. Verify email
        code = get_redis().get("verification:onboard@example.com:register")
        resp = client.post(
            "/api/v1/auth/register/verify",
            json={"email": "onboard@example.com", "code": code, "password": "Pass1234"},
        )
        assert resp.json()["code"] == Code.OK
        tokens = resp.json()["data"]
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # 3. View initial profile
        resp = client.get("/api/v1/user/me", headers=headers)
        assert resp.json()["code"] == Code.OK
        profile = resp.json()["data"]
        assert profile["email"] == "onboard@example.com"
        assert profile["username"].startswith("user_")

        # 4. Update profile
        resp = client.post(
            "/api/v1/user/me",
            headers=headers,
            json={"avatar_url": "https://example.com/avatar.png"},
        )
        assert resp.json()["code"] == Code.OK
        assert resp.json()["data"]["avatar_url"] == "https://example.com/avatar.png"

        # 5. Logout
        resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": tokens["refresh_token"]},
        )
        assert resp.json()["code"] == Code.OK

    async def test_invitation_onboarding(
        self, client: TestClient, session: AsyncSession, monkeypatch, mock_email: list
    ):
        """Invitation code -> register -> verify -> login -> access service."""
        monkeypatch.setattr(config_module.settings, "require_invitation_code", True)

        inv = InvitationCode(code="WELCOME", max_uses=10, used_count=0, is_active=True)
        session.add(inv)
        await session.commit()
        await session.refresh(inv)

        # 1. Register with invitation code
        resp = client.post(
            "/api/v1/auth/register",
            json={
                "email": "invited@example.com",
                "password": "Pass1234",
                "invitation_code": "WELCOME",
            },
        )
        assert resp.json()["code"] == Code.OK
        assert len(mock_email) == 1

        # 2. Verify email
        code = get_redis().get("verification:invited@example.com:register")
        resp = client.post(
            "/api/v1/auth/register/verify",
            json={"email": "invited@example.com", "code": code, "password": "Pass1234"},
        )
        assert resp.json()["code"] == Code.OK

        # 3. Verify invitation used_count
        await session.refresh(inv)
        assert inv.used_count == 1

        # 4. Login with the new account
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "invited@example.com", "password": "Pass1234"},
        )
        assert resp.json()["code"] == Code.OK
        headers = {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}

        # 5. Access profile
        resp = client.get("/api/v1/user/me", headers=headers)
        assert resp.json()["code"] == Code.OK
        assert resp.json()["data"]["email"] == "invited@example.com"


class TestTokenLifecycle:
    """Verify the full lifecycle of access and refresh tokens."""

    def test_access_refresh_logout(self, client: TestClient, register_and_verify):
        """Register -> access API -> refresh -> access again -> logout -> verify revoked."""
        body = register_and_verify("tokenlife@example.com", "Pass1234")
        access_token = body["data"]["access_token"]
        refresh_token = body["data"]["refresh_token"]

        # 1. Access API with original access token
        resp = client.get(
            "/api/v1/user/whoami",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.json()["code"] == Code.OK

        # 2. Refresh to get new token pair
        resp = client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.json()["code"] == Code.OK
        new_access = resp.json()["data"]["access_token"]
        new_refresh = resp.json()["data"]["refresh_token"]
        # Refresh token must change (token rotation)
        assert new_refresh != refresh_token

        # 3. Access API with NEW access token
        resp = client.get(
            "/api/v1/user/whoami",
            headers={"Authorization": f"Bearer {new_access}"},
        )
        assert resp.json()["code"] == Code.OK
        assert resp.json()["data"]["username"].startswith("user_")

        # 4. Old refresh token is revoked (token rotation)
        resp = client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.json()["code"] == Code.UNAUTHORIZED

        # 5. Logout with new refresh token
        resp = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": new_refresh},
        )
        assert resp.json()["code"] == Code.OK

        # 6. New refresh token is now revoked too
        resp = client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": new_refresh},
        )
        assert resp.json()["code"] == Code.UNAUTHORIZED


class TestMultiSession:
    """Verify concurrent sessions (multi-device login) work independently."""

    def test_two_sessions_independent_logout(self, client: TestClient, register_and_verify):
        """Login twice -> two sessions -> logout one -> other still works."""
        register_and_verify("multi@example.com", "Pass1234")

        # Session 1: login
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "multi@example.com", "password": "Pass1234"},
        )
        assert resp.json()["code"] == Code.OK
        s1_access = resp.json()["data"]["access_token"]
        s1_refresh = resp.json()["data"]["refresh_token"]

        # Session 2: login again (different device)
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "multi@example.com", "password": "Pass1234"},
        )
        assert resp.json()["code"] == Code.OK
        s2_access = resp.json()["data"]["access_token"]
        s2_refresh = resp.json()["data"]["refresh_token"]

        # Both sessions can access API
        resp = client.get("/api/v1/user/whoami", headers={"Authorization": f"Bearer {s1_access}"})
        assert resp.json()["code"] == Code.OK
        resp = client.get("/api/v1/user/whoami", headers={"Authorization": f"Bearer {s2_access}"})
        assert resp.json()["code"] == Code.OK

        # Logout session 1
        resp = client.post("/api/v1/auth/logout", json={"refresh_token": s1_refresh})
        assert resp.json()["code"] == Code.OK

        # Session 1 refresh is revoked
        resp = client.post("/api/v1/auth/token/refresh", json={"refresh_token": s1_refresh})
        assert resp.json()["code"] == Code.UNAUTHORIZED

        # Session 2 is unaffected
        resp = client.get("/api/v1/user/whoami", headers={"Authorization": f"Bearer {s2_access}"})
        assert resp.json()["code"] == Code.OK
        resp = client.post("/api/v1/auth/token/refresh", json={"refresh_token": s2_refresh})
        assert resp.json()["code"] == Code.OK


class TestPasswordLifecycle:
    """Verify password change and reset across the full user lifecycle."""

    def test_change_then_reset(self, client: TestClient, register_and_verify, mock_email: list):
        """Register -> change password -> logout -> login -> forgot -> reset -> login."""
        body = register_and_verify("pwlife@example.com", "Original1")
        headers = {"Authorization": f"Bearer {body['data']['access_token']}"}
        refresh_token = body["data"]["refresh_token"]

        # 1. Change password
        resp = client.post(
            "/api/v1/user/password/change",
            headers=headers,
            json={"old_password": "Original1", "new_password": "Changed1"},
        )
        assert resp.json()["code"] == Code.OK

        # 2. Logout
        client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})

        # 3. Old password no longer works
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "pwlife@example.com", "password": "Original1"},
        )
        assert resp.json()["code"] == Code.UNAUTHORIZED

        # 4. New password works
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "pwlife@example.com", "password": "Changed1"},
        )
        assert resp.json()["code"] == Code.OK

        # 5. Forgot password
        mock_email.clear()
        client.post("/api/v1/auth/password/forgot", json={"email": "pwlife@example.com"})
        assert len(mock_email) == 1

        # 6. Reset password
        code = get_redis().get("verification:pwlife@example.com:reset_password")
        resp = client.post(
            "/api/v1/auth/password/reset",
            json={"email": "pwlife@example.com", "code": code, "new_password": "ResetPw1"},
        )
        assert resp.json()["code"] == Code.OK

        # 7. Login with reset password
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "pwlife@example.com", "password": "ResetPw1"},
        )
        assert resp.json()["code"] == Code.OK

    def test_change_password_revokes_refresh_tokens(self, client: TestClient, register_and_verify):
        """Changing password should revoke refresh tokens for security."""
        body = register_and_verify("preserve@example.com", "Pass1234")
        access_token = body["data"]["access_token"]
        refresh_token = body["data"]["refresh_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # Change password
        resp = client.post(
            "/api/v1/user/password/change",
            headers=headers,
            json={"old_password": "Pass1234", "new_password": "NewPass1"},
        )
        assert resp.json()["code"] == Code.OK

        # Access token still works (JWT is stateless, valid until expiry)
        resp = client.get("/api/v1/user/me", headers=headers)
        assert resp.json()["code"] == Code.OK

        # Refresh token is revoked
        resp = client.post("/api/v1/auth/token/refresh", json={"refresh_token": refresh_token})
        assert resp.json()["code"] == Code.UNAUTHORIZED


class TestProfilePersistence:
    """Verify profile data persists across sessions."""

    def test_profile_survives_relogin(self, client: TestClient, register_and_verify):
        """Update profile -> logout -> login again -> profile data persisted."""
        body = register_and_verify("persist@example.com", "Pass1234")
        headers = {"Authorization": f"Bearer {body['data']['access_token']}"}

        # Update profile
        resp = client.post(
            "/api/v1/user/me",
            headers=headers,
            json={"avatar_url": "https://example.com/photo.jpg"},
        )
        assert resp.json()["code"] == Code.OK

        # Logout
        client.post("/api/v1/auth/logout", json={"refresh_token": body["data"]["refresh_token"]})

        # Login again
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "persist@example.com", "password": "Pass1234"},
        )
        new_token = resp.json()["data"]["access_token"]

        # Profile data persisted
        resp = client.get(
            "/api/v1/user/me",
            headers={"Authorization": f"Bearer {new_token}"},
        )
        assert resp.json()["code"] == Code.OK
        data = resp.json()["data"]
        assert data["avatar_url"] == "https://example.com/photo.jpg"
