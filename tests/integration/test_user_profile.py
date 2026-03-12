"""Integration tests for user profile and password change endpoints."""

from fastapi.testclient import TestClient

from common.resp import Code


class TestProtectedEndpoints:
    """Tests for protected endpoints requiring authentication."""

    def test_whoami_without_token(self, client: TestClient):
        response = client.get("/api/v1/user/whoami")
        assert response.json()["code"] == Code.UNAUTHORIZED

    def test_whoami_with_valid_token(self, client: TestClient, auth_header):
        headers = auth_header("auth@example.com", "AuthPass1")
        response = client.get("/api/v1/user/whoami", headers=headers)
        assert response.json()["code"] == Code.OK
        assert response.json()["data"]["username"].startswith("user_")

    def test_whoami_with_invalid_token(self, client: TestClient):
        response = client.get(
            "/api/v1/user/whoami",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert response.json()["code"] == Code.UNAUTHORIZED


class TestUserProfile:
    """Tests for /user/me endpoint."""

    def test_get_me_success(self, client: TestClient, auth_header):
        headers = auth_header("profile@example.com", "Password1")
        response = client.get("/api/v1/user/me", headers=headers)
        assert response.json()["code"] == Code.OK
        data = response.json()["data"]
        assert data["username"].startswith("user_")
        assert data["email"] == "profile@example.com"
        assert data["is_active"] is True

    def test_update_me_success(self, client: TestClient, auth_header):
        headers = auth_header("update@example.com", "Password1")
        response = client.post(
            "/api/v1/user/me",
            headers=headers,
            json={"avatar_url": "https://example.com/avatar.png"},
        )
        assert response.json()["code"] == Code.OK
        data = response.json()["data"]
        assert data["avatar_url"] == "https://example.com/avatar.png"


class TestUsernameChange:
    """Tests for username change via POST /user/me."""

    def test_change_username_success(self, client: TestClient, auth_header):
        headers = auth_header("rename@example.com", "Password1")
        response = client.post(
            "/api/v1/user/me",
            headers=headers,
            json={"username": "my-new-name"},
        )
        assert response.json()["code"] == Code.OK
        data = response.json()["data"]
        assert data["username"] == "my-new-name"
        assert "access_token" in data
        assert "refresh_token" in data

        # Old token should fail (username in JWT is stale)
        old_resp = client.get("/api/v1/user/me", headers=headers)
        assert old_resp.json()["code"] != Code.OK

        # New token should work
        new_headers = {"Authorization": f"Bearer {data['access_token']}"}
        new_resp = client.get("/api/v1/user/me", headers=new_headers)
        assert new_resp.json()["code"] == Code.OK
        assert new_resp.json()["data"]["username"] == "my-new-name"

    def test_change_username_conflict(self, client: TestClient, auth_header):
        headers_a = auth_header("usera@example.com", "Password1")
        # Set user A's username to a known value
        client.post("/api/v1/user/me", headers=headers_a, json={"username": "taken-name"})

        headers_b = auth_header("userb@example.com", "Password1")
        response = client.post(
            "/api/v1/user/me",
            headers=headers_b,
            json={"username": "taken-name"},
        )
        assert response.json()["code"] == Code.CONFLICT

    def test_change_username_invalid_format(self, client: TestClient, auth_header):
        headers = auth_header("fmt@example.com", "Password1")
        response = client.post(
            "/api/v1/user/me",
            headers=headers,
            json={"username": "ab"},  # too short
        )
        assert response.json()["code"] == Code.BAD_REQUEST


class TestPasswordChange:
    """Tests for /user/password/change endpoint."""

    def test_change_password_success(self, client: TestClient, auth_header):
        headers = auth_header("change@example.com", "OldPass1")
        response = client.post(
            "/api/v1/user/password/change",
            headers=headers,
            json={"old_password": "OldPass1", "new_password": "NewPass1"},
        )
        assert response.json()["code"] == Code.OK

        # Login with new password
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "change@example.com", "password": "NewPass1"},
        )
        assert login_resp.json()["code"] == Code.OK

    def test_change_password_wrong_old(self, client: TestClient, auth_header):
        headers = auth_header("wrongold@example.com", "Correct1")
        response = client.post(
            "/api/v1/user/password/change",
            headers=headers,
            json={"old_password": "wrong", "new_password": "NewPass1"},
        )
        assert response.json()["code"] == Code.BAD_REQUEST
