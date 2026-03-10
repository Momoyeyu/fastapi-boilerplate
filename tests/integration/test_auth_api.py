"""
Integration tests for Auth API endpoints.

Tests the complete request/response cycle including database operations.
"""

from fastapi.testclient import TestClient

from common.resp import Code

ENVELOPE_KEYS = {"code", "message", "data"}


def register_and_verify(client: TestClient, email: str, password: str) -> dict:
    """Helper to register a user through the two-step process."""
    from conf.redis import get_redis

    # Step 1: Initiate registration
    client.post("/auth/register", json={"email": email, "password": password})

    # Get verification code from Redis
    key = f"verification:{email.lower()}:register"
    code = get_redis().get(key)

    # Step 2: Verify and complete registration
    response = client.post(
        "/auth/register/verify",
        json={"email": email, "code": code, "password": password},
    )
    return response.json()


class TestAuthRegister:
    """Tests for POST /auth/register endpoint."""

    def test_register_initiate_success(self, client: TestClient):
        """Test successful registration initiation."""
        response = client.post(
            "/auth/register",
            json={"email": "test@example.com", "password": "secret123"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == Code.OK
        assert "Verification code sent" in body["message"]

    def test_register_verify_success(self, client: TestClient):
        """Test successful registration verification."""
        body = register_and_verify(client, "newuser@example.com", "secret123")
        assert body["code"] == Code.OK
        data = body["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    def test_register_duplicate_email(self, client: TestClient):
        """Test registration fails for duplicate email."""
        register_and_verify(client, "duplicate@example.com", "pass123")

        response = client.post(
            "/auth/register",
            json={"email": "duplicate@example.com", "password": "different"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.CONFLICT


class TestAuthLogin:
    """Tests for POST /auth/login endpoint."""

    def test_login_success(self, client: TestClient):
        """Test successful login returns token data in envelope."""
        register_and_verify(client, "login@example.com", "secret123")

        response = client.post(
            "/auth/login",
            data={"username": "login@example.com", "password": "secret123"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == Code.OK
        data = body["data"]
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        assert isinstance(data["expires_in"], int)
        assert data["expires_in"] > 0
        assert "refresh_token" in data
        assert len(data["refresh_token"]) > 0
        assert "refresh_token_expires_in" in data

    def test_login_with_username(self, client: TestClient):
        """Test login with username instead of email."""
        register_and_verify(client, "username_test@example.com", "secret123")

        response = client.post(
            "/auth/login",
            data={"username": "username_test", "password": "secret123"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

    def test_login_wrong_password(self, client: TestClient):
        """Test login fails with wrong password."""
        register_and_verify(client, "wrongpass@example.com", "correct_pass")

        response = client.post(
            "/auth/login",
            data={"username": "wrongpass@example.com", "password": "wrong_pass"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.UNAUTHORIZED

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login fails for non-existent user."""
        response = client.post(
            "/auth/login",
            data={"username": "nonexistent@example.com", "password": "anypass"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.UNAUTHORIZED


class TestRefreshToken:
    """Tests for POST /auth/token/refresh endpoint."""

    def test_refresh_success(self, client: TestClient):
        """Test successful token refresh returns new token pair."""
        body = register_and_verify(client, "refresh@example.com", "secret123")
        refresh_token = body["data"]["refresh_token"]

        response = client.post(
            "/auth/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == Code.OK
        data = body["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["refresh_token"] != refresh_token

    def test_refresh_with_invalid_token(self, client: TestClient):
        """Test refresh fails with invalid token."""
        response = client.post(
            "/auth/token/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.UNAUTHORIZED

    def test_refresh_with_revoked_token(self, client: TestClient):
        """Test refresh fails with already used (revoked) token."""
        body = register_and_verify(client, "revoked@example.com", "secret123")
        refresh_token = body["data"]["refresh_token"]

        # First refresh should succeed
        first_refresh = client.post(
            "/auth/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert first_refresh.status_code == 200
        assert first_refresh.json()["code"] == Code.OK

        # Second refresh with same token should fail (Token Rotation)
        second_refresh = client.post(
            "/auth/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert second_refresh.status_code == 200
        assert second_refresh.json()["code"] == Code.UNAUTHORIZED


class TestLogout:
    """Tests for POST /auth/logout endpoint."""

    def test_logout_success(self, client: TestClient):
        """Test successful logout revokes refresh token."""
        body = register_and_verify(client, "logout@example.com", "secret123")
        refresh_token = body["data"]["refresh_token"]

        response = client.post(
            "/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK
        assert response.json()["message"] == "Successfully logged out"

        # Try to use the revoked refresh token
        refresh_response = client.post(
            "/auth/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 200
        assert refresh_response.json()["code"] == Code.UNAUTHORIZED

    def test_logout_with_invalid_token(self, client: TestClient):
        """Test logout with invalid token still returns success (idempotent)."""
        response = client.post(
            "/auth/logout",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK


class TestEmailVerification:
    """Tests for email sending during auth flows."""

    def test_register_sends_verification_email(self, client: TestClient, mock_email: list):
        """Verify registration triggers email with correct purpose and 6-digit code."""
        client.post("/auth/register", json={"email": "emailtest@example.com", "password": "pass123"})
        assert len(mock_email) == 1
        assert mock_email[0]["email"] == "emailtest@example.com"
        assert mock_email[0]["purpose"] == "register"
        assert len(mock_email[0]["code"]) == 6

    def test_password_forgot_sends_email(self, client: TestClient, mock_email: list):
        """Verify password forgot sends email with reset_password purpose."""
        register_and_verify(client, "forgotemail@example.com", "pass123")
        mock_email.clear()

        client.post("/auth/password/forgot", json={"email": "forgotemail@example.com"})
        assert len(mock_email) == 1
        assert mock_email[0]["email"] == "forgotemail@example.com"
        assert mock_email[0]["purpose"] == "reset_password"

    def test_password_forgot_no_email_for_nonexistent(self, client: TestClient, mock_email: list):
        """Verify no email sent for non-existent user (anti-enumeration)."""
        client.post("/auth/password/forgot", json={"email": "nobody@example.com"})
        assert len(mock_email) == 0


class TestVerificationCode:
    """Tests for verification code edge cases."""

    def test_register_wrong_code_fails(self, client: TestClient):
        """Test registration fails with wrong verification code."""
        client.post("/auth/register", json={"email": "wrongcode@example.com", "password": "pass123"})
        response = client.post(
            "/auth/register/verify",
            json={"email": "wrongcode@example.com", "code": "000000", "password": "pass123"},
        )
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_register_code_consumed_after_use(self, client: TestClient):
        """Test verification code is consumed and can't be reused."""
        from conf.redis import get_redis

        register_and_verify(client, "consumed@example.com", "pass123")
        key = "verification:consumed@example.com:register"
        assert get_redis().get(key) is None

    def test_password_reset_wrong_code_fails(self, client: TestClient):
        """Test password reset fails with wrong code."""
        register_and_verify(client, "resetwrong@example.com", "pass123")
        client.post("/auth/password/forgot", json={"email": "resetwrong@example.com"})
        response = client.post(
            "/auth/password/reset",
            json={"email": "resetwrong@example.com", "code": "000000", "new_password": "newpass"},
        )
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_password_reset_code_consumed(self, client: TestClient):
        """Test password reset code is consumed and can't be reused."""
        from conf.redis import get_redis

        register_and_verify(client, "resetonce@example.com", "pass123")
        client.post("/auth/password/forgot", json={"email": "resetonce@example.com"})

        key = "verification:resetonce@example.com:reset_password"
        code = get_redis().get(key)

        # First reset succeeds
        resp1 = client.post(
            "/auth/password/reset",
            json={"email": "resetonce@example.com", "code": code, "new_password": "newpass"},
        )
        assert resp1.json()["code"] == Code.OK

        # Second reset with same code fails
        resp2 = client.post(
            "/auth/password/reset",
            json={"email": "resetonce@example.com", "code": code, "new_password": "newpass2"},
        )
        assert resp2.json()["code"] == Code.BAD_REQUEST


class TestPasswordReset:
    """Tests for password reset endpoints."""

    def test_password_forgot_success(self, client: TestClient):
        """Test password forgot sends verification code."""
        register_and_verify(client, "forgot@example.com", "secret123")

        response = client.post(
            "/auth/password/forgot",
            json={"email": "forgot@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

    def test_password_forgot_nonexistent_email(self, client: TestClient):
        """Test password forgot for non-existent email returns success (no enumeration)."""
        response = client.post(
            "/auth/password/forgot",
            json={"email": "nonexistent@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

    def test_password_reset_success(self, client: TestClient):
        """Test password reset with valid code."""
        from conf.redis import get_redis

        register_and_verify(client, "reset@example.com", "oldpass")

        # Request password reset
        client.post("/auth/password/forgot", json={"email": "reset@example.com"})

        # Get verification code
        key = "verification:reset@example.com:reset_password"
        code = get_redis().get(key)

        # Reset password
        response = client.post(
            "/auth/password/reset",
            json={"email": "reset@example.com", "code": code, "new_password": "newpass"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

        # Login with new password
        login_response = client.post(
            "/auth/login",
            data={"username": "reset@example.com", "password": "newpass"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["code"] == Code.OK
