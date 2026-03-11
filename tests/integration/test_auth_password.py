"""Integration tests for password forgot and reset flows."""

from fastapi.testclient import TestClient

from common.resp import Code
from conf.redis import get_redis


class TestPasswordForgot:
    """Tests for POST /auth/password/forgot endpoint."""

    def test_forgot_success(self, client: TestClient, register_and_verify):
        register_and_verify("forgot@example.com", "Secret12")

        response = client.post(
            "/api/v1/auth/password/forgot",
            json={"email": "forgot@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

    def test_forgot_nonexistent_email(self, client: TestClient):
        """Returns success to prevent email enumeration."""
        response = client.post(
            "/api/v1/auth/password/forgot",
            json={"email": "nonexistent@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["code"] == Code.OK

    def test_forgot_sends_email(self, client: TestClient, register_and_verify, mock_email: list):
        register_and_verify("forgotemail@example.com", "Pass1234")
        mock_email.clear()

        client.post("/api/v1/auth/password/forgot", json={"email": "forgotemail@example.com"})
        assert len(mock_email) == 1
        assert mock_email[0]["email"] == "forgotemail@example.com"
        assert mock_email[0]["purpose"] == "reset_password"

    def test_forgot_no_email_for_nonexistent(self, client: TestClient, mock_email: list):
        """No email sent for non-existent user (anti-enumeration)."""
        client.post("/api/v1/auth/password/forgot", json={"email": "nobody@example.com"})
        assert len(mock_email) == 0


class TestPasswordReset:
    """Tests for POST /auth/password/reset endpoint."""

    def test_reset_success(self, client: TestClient, register_and_verify):
        """Full flow: register → forgot → get code → reset → login with new password."""
        register_and_verify("reset@example.com", "OldPass1")

        client.post("/api/v1/auth/password/forgot", json={"email": "reset@example.com"})
        code = get_redis().get("verification:reset@example.com:reset_password")

        response = client.post(
            "/api/v1/auth/password/reset",
            json={"email": "reset@example.com", "code": code, "new_password": "NewPass1"},
        )
        assert response.json()["code"] == Code.OK

        # Login with new password
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "reset@example.com", "password": "NewPass1"},
        )
        assert login_resp.json()["code"] == Code.OK

    def test_reset_wrong_code_fails(self, client: TestClient, register_and_verify):
        register_and_verify("resetwrong@example.com", "Pass1234")
        client.post("/api/v1/auth/password/forgot", json={"email": "resetwrong@example.com"})
        response = client.post(
            "/api/v1/auth/password/reset",
            json={"email": "resetwrong@example.com", "code": "000000", "new_password": "NewPass1"},
        )
        assert response.json()["code"] == Code.BAD_REQUEST

    def test_reset_code_consumed(self, client: TestClient, register_and_verify):
        """Verification code is single-use: second attempt with same code fails."""
        register_and_verify("resetonce@example.com", "Pass1234")
        client.post("/api/v1/auth/password/forgot", json={"email": "resetonce@example.com"})

        code = get_redis().get("verification:resetonce@example.com:reset_password")

        resp1 = client.post(
            "/api/v1/auth/password/reset",
            json={"email": "resetonce@example.com", "code": code, "new_password": "NewPass1"},
        )
        assert resp1.json()["code"] == Code.OK

        resp2 = client.post(
            "/api/v1/auth/password/reset",
            json={"email": "resetonce@example.com", "code": code, "new_password": "newpass2"},
        )
        assert resp2.json()["code"] == Code.BAD_REQUEST
