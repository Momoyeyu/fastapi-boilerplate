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
        assert response.json()["data"]["username"] == "auth"

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
        assert data["username"] == "profile"
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
