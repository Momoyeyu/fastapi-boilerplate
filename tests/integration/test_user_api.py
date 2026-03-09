"""
Integration tests for User API endpoints.

Tests the complete request/response cycle including database operations.
"""

from fastapi.testclient import TestClient

from common.resp import Code


def register_and_verify(client: TestClient, email: str, password: str) -> dict:
    """Helper to register a user through the two-step process."""
    from conf.redis import get_redis

    client.post("/auth/register", json={"email": email, "password": password})
    key = f"verification:{email.lower()}:register"
    code = get_redis().get(key)
    response = client.post(
        "/auth/register/verify",
        json={"email": email, "code": code, "password": password},
    )
    return response.json()


def get_auth_header(client: TestClient, email: str, password: str) -> dict:
    """Helper to get auth header for a user."""
    body = register_and_verify(client, email, password)
    return {"Authorization": f"Bearer {body['data']['access_token']}"}


class TestProtectedEndpoints:
    """Tests for protected endpoints requiring authentication."""

    def test_whoami_without_token(self, client: TestClient):
        """Test accessing /user/whoami without token returns unauthorized."""
        response = client.get("/user/whoami")
        assert response.status_code == 200
        assert response.json()["code"] == Code.UNAUTHORIZED

    def test_whoami_with_valid_token(self, client: TestClient):
        """Test accessing /user/whoami with valid token returns username."""
        headers = get_auth_header(client, "auth@example.com", "authpass")

        response = client.get("/user/whoami", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == Code.OK
        assert body["data"]["username"] == "auth"

    def test_whoami_with_invalid_token(self, client: TestClient):
        """Test accessing /user/whoami with invalid token returns unauthorized."""
        response = client.get(
            "/user/whoami",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.UNAUTHORIZED


class TestUserProfile:
    """Tests for /user/me endpoint."""

    def test_get_me_success(self, client: TestClient):
        """Test GET /user/me returns user profile."""
        headers = get_auth_header(client, "profile@example.com", "password")

        response = client.get("/user/me", headers=headers)
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == Code.OK
        data = body["data"]
        assert data["username"] == "profile"
        assert data["email"] == "profile@example.com"
        assert data["role"] == "user"
        assert data["is_active"] is True

    def test_update_me_success(self, client: TestClient):
        """Test POST /user/me updates user profile."""
        headers = get_auth_header(client, "update@example.com", "password")

        response = client.post(
            "/user/me",
            headers=headers,
            json={"nickname": "New Nick", "avatar_url": "https://example.com/avatar.png"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["code"] == Code.OK
        data = body["data"]
        assert data["nickname"] == "New Nick"
        assert data["avatar_url"] == "https://example.com/avatar.png"


class TestPasswordChange:
    """Tests for /user/password/change endpoint."""

    def test_change_password_success(self, client: TestClient):
        """Test successful password change."""
        headers = get_auth_header(client, "change@example.com", "oldpass")

        response = client.post(
            "/user/password/change",
            headers=headers,
            json={"old_password": "oldpass", "new_password": "newpass"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

        # Login with new password
        login_response = client.post(
            "/auth/login",
            data={"username": "change@example.com", "password": "newpass"},
        )
        assert login_response.status_code == 200
        assert login_response.json()["code"] == Code.OK

    def test_change_password_wrong_old(self, client: TestClient):
        """Test password change fails with wrong old password."""
        headers = get_auth_header(client, "wrongold@example.com", "correct")

        response = client.post(
            "/user/password/change",
            headers=headers,
            json={"old_password": "wrong", "new_password": "newpass"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.BAD_REQUEST
