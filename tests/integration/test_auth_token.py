"""Integration tests for login, token refresh, and logout flows."""

from fastapi.testclient import TestClient

from common.resp import Code


class TestAuthLogin:
    """Tests for POST /auth/login endpoint (JSON body)."""

    def test_login_success(self, client: TestClient, register_and_verify):
        """Test successful login returns token data in envelope."""
        register_and_verify("login@example.com", "Secret12")

        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": "login@example.com", "password": "Secret12"},
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

    def test_login_with_username(self, client: TestClient, register_and_verify):
        """Test login with username instead of email."""
        body = register_and_verify("username_test@example.com", "Secret12")
        token = body["data"]["access_token"]
        whoami = client.get("/api/v1/user/whoami", headers={"Authorization": f"Bearer {token}"})
        username = whoami.json()["data"]["username"]

        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": username, "password": "Secret12"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

    def test_login_wrong_password(self, client: TestClient, register_and_verify):
        """Test login fails with wrong password."""
        register_and_verify("wrongpass@example.com", "correct_pass")

        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": "wrongpass@example.com", "password": "wrong_pass"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == Code.UNAUTHORIZED

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login fails for non-existent user."""
        response = client.post(
            "/api/v1/auth/login",
            json={"identifier": "nonexistent@example.com", "password": "anypass"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == Code.UNAUTHORIZED


class TestRefreshToken:
    """Tests for POST /auth/token/refresh endpoint."""

    def test_refresh_success(self, client: TestClient, register_and_verify):
        """Test successful token refresh returns new token pair."""
        body = register_and_verify("refresh@example.com", "Secret12")
        refresh_token = body["data"]["refresh_token"]

        response = client.post(
            "/api/v1/auth/token/refresh",
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
            "/api/v1/auth/token/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401
        assert response.json()["code"] == Code.UNAUTHORIZED

    def test_refresh_with_revoked_token(self, client: TestClient, register_and_verify):
        """Test refresh fails with already used (revoked) token."""
        body = register_and_verify("revoked@example.com", "Secret12")
        refresh_token = body["data"]["refresh_token"]

        # First refresh should succeed
        first_refresh = client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert first_refresh.json()["code"] == Code.OK

        # Second refresh with same token should fail (Token Rotation)
        second_refresh = client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert second_refresh.json()["code"] == Code.UNAUTHORIZED


class TestLogout:
    """Tests for POST /auth/logout endpoint."""

    def test_logout_success(self, client: TestClient, register_and_verify):
        """Test successful logout revokes refresh token."""
        body = register_and_verify("logout@example.com", "Secret12")
        refresh_token = body["data"]["refresh_token"]

        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK
        assert response.json()["message"] == "Successfully logged out"

        # Try to use the revoked refresh token
        refresh_response = client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.json()["code"] == Code.UNAUTHORIZED

    def test_logout_with_invalid_token(self, client: TestClient):
        """Test logout with invalid token still returns success (idempotent)."""
        response = client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK
