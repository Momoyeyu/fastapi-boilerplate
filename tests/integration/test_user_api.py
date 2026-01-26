"""
Integration tests for User API endpoints.

Tests the complete request/response cycle including database operations.
"""

from fastapi.testclient import TestClient


class TestUserRegister:
    """Tests for POST /user/register endpoint."""

    def test_register_success(self, client: TestClient):
        """Test successful user registration."""
        response = client.post(
            "/user/register",
            json={"username": "testuser", "password": "testpass123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert "id" in data
        assert isinstance(data["id"], int)

    def test_register_duplicate_username(self, client: TestClient):
        """Test registration fails for duplicate username."""
        # First registration should succeed
        response1 = client.post(
            "/user/register",
            json={"username": "duplicate_user", "password": "pass123"},
        )
        assert response1.status_code == 200

        # Second registration with same username should fail
        response2 = client.post(
            "/user/register",
            json={"username": "duplicate_user", "password": "different_pass"},
        )
        assert response2.status_code == 409
        assert "already exists" in response2.json()["detail"].lower()


class TestUserLogin:
    """Tests for POST /user/login endpoint."""

    def test_login_success(self, client: TestClient):
        """Test successful login returns OAuth2 compliant token response with refresh token."""
        # Register user first
        client.post(
            "/user/register",
            json={"username": "login_user", "password": "secret123"},
        )

        # Login (OAuth2 form-data format)
        response = client.post(
            "/user/login",
            data={"username": "login_user", "password": "secret123"},
        )
        assert response.status_code == 200
        data = response.json()
        # OAuth2 required fields (RFC 6749 Section 5.1)
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert len(data["access_token"]) > 0
        # expires_in is RECOMMENDED by RFC 6749
        assert "expires_in" in data
        assert isinstance(data["expires_in"], int)
        assert data["expires_in"] > 0
        # Refresh token fields
        assert "refresh_token" in data
        assert len(data["refresh_token"]) > 0
        assert "refresh_token_expires_in" in data
        assert isinstance(data["refresh_token_expires_in"], int)
        assert data["refresh_token_expires_in"] > 0

    def test_login_wrong_password(self, client: TestClient):
        """Test login fails with wrong password returns OAuth2 error."""
        # Register user first
        client.post(
            "/user/register",
            json={"username": "wrong_pass_user", "password": "correct_pass"},
        )

        # Try login with wrong password (OAuth2 form-data format)
        response = client.post(
            "/user/login",
            data={"username": "wrong_pass_user", "password": "wrong_pass"},
        )
        # OAuth2 error response (RFC 6749 Section 5.2)
        assert response.status_code == 400
        data = response.json()["detail"]
        assert data["error"] == "invalid_grant"
        assert "error_description" in data

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login fails for non-existent user returns OAuth2 error."""
        response = client.post(
            "/user/login",
            data={"username": "nonexistent", "password": "anypass"},
        )
        # OAuth2 error response (RFC 6749 Section 5.2)
        assert response.status_code == 400
        data = response.json()["detail"]
        assert data["error"] == "invalid_grant"
        assert "error_description" in data


class TestRefreshToken:
    """Tests for POST /user/refresh endpoint."""

    def test_refresh_success(self, client: TestClient):
        """Test successful token refresh returns new token pair."""
        # Register and login
        client.post(
            "/user/register",
            json={"username": "refresh_user", "password": "secret123"},
        )
        login_response = client.post(
            "/user/login",
            data={"username": "refresh_user", "password": "secret123"},
        )
        login_data = login_response.json()
        refresh_token = login_data["refresh_token"]

        # Refresh tokens
        response = client.post(
            "/user/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert "expires_in" in data
        assert "refresh_token_expires_in" in data
        # New refresh token should be different (Token Rotation)
        assert data["refresh_token"] != refresh_token

    def test_refresh_with_invalid_token(self, client: TestClient):
        """Test refresh fails with invalid token."""
        response = client.post(
            "/user/refresh",
            json={"refresh_token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_refresh_with_revoked_token(self, client: TestClient):
        """Test refresh fails with already used (revoked) token."""
        # Register and login
        client.post(
            "/user/register",
            json={"username": "revoked_user", "password": "secret123"},
        )
        login_response = client.post(
            "/user/login",
            data={"username": "revoked_user", "password": "secret123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # First refresh should succeed
        first_refresh = client.post(
            "/user/refresh",
            json={"refresh_token": refresh_token},
        )
        assert first_refresh.status_code == 200

        # Second refresh with same token should fail (Token Rotation)
        second_refresh = client.post(
            "/user/refresh",
            json={"refresh_token": refresh_token},
        )
        assert second_refresh.status_code == 401


class TestLogout:
    """Tests for POST /user/logout endpoint."""

    def test_logout_success(self, client: TestClient):
        """Test successful logout revokes refresh token."""
        # Register and login
        client.post(
            "/user/register",
            json={"username": "logout_user", "password": "secret123"},
        )
        login_response = client.post(
            "/user/login",
            data={"username": "logout_user", "password": "secret123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        # Logout
        response = client.post(
            "/user/logout",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Successfully logged out"

        # Try to use the revoked refresh token
        refresh_response = client.post(
            "/user/refresh",
            json={"refresh_token": refresh_token},
        )
        assert refresh_response.status_code == 401

    def test_logout_with_invalid_token(self, client: TestClient):
        """Test logout with invalid token still returns success (idempotent)."""
        response = client.post(
            "/user/logout",
            json={"refresh_token": "invalid-token"},
        )
        # Logout is idempotent - should succeed even with invalid token
        assert response.status_code == 200


class TestProtectedEndpoints:
    """Tests for protected endpoints requiring authentication."""

    def test_whoami_without_token(self, client: TestClient):
        """Test accessing /user/whoami without token returns 401."""
        response = client.get("/user/whoami")
        assert response.status_code == 401

    def test_whoami_with_valid_token(self, client: TestClient):
        """Test accessing /user/whoami with valid token returns username."""
        # Register and login
        client.post(
            "/user/register",
            json={"username": "auth_user", "password": "authpass"},
        )
        login_response = client.post(
            "/user/login",
            data={"username": "auth_user", "password": "authpass"},
        )
        token = login_response.json()["access_token"]

        # Access protected endpoint
        response = client.get(
            "/user/whoami",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["username"] == "auth_user"

    def test_whoami_with_invalid_token(self, client: TestClient):
        """Test accessing /user/whoami with invalid token returns 401."""
        response = client.get(
            "/user/whoami",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 401
