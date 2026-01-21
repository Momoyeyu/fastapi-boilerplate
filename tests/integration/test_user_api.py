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
        """Test successful login returns JWT token in header."""
        # Register user first
        client.post(
            "/user/register",
            json={"username": "login_user", "password": "secret123"},
        )

        # Login
        response = client.post(
            "/user/login",
            json={"username": "login_user", "password": "secret123"},
        )
        assert response.status_code == 200
        assert "x-jwt-token" in response.headers
        token = response.headers["x-jwt-token"]
        assert len(token) > 0

    def test_login_wrong_password(self, client: TestClient):
        """Test login fails with wrong password."""
        # Register user first
        client.post(
            "/user/register",
            json={"username": "wrong_pass_user", "password": "correct_pass"},
        )

        # Try login with wrong password
        response = client.post(
            "/user/login",
            json={"username": "wrong_pass_user", "password": "wrong_pass"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login fails for non-existent user."""
        response = client.post(
            "/user/login",
            json={"username": "nonexistent", "password": "anypass"},
        )
        assert response.status_code == 401


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
            json={"username": "auth_user", "password": "authpass"},
        )
        token = login_response.headers["x-jwt-token"]

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
