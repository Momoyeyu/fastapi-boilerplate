"""
Integration tests for response envelope format.

Verifies that ALL responses (success and error) follow the
standardized envelope: {code, message, data}.
"""

from fastapi.testclient import TestClient

from common.resp import Code

ENVELOPE_KEYS = {"code", "message", "data"}


class TestErrorResponseFormat:
    """Error responses use proper HTTP status codes with {code, message, data} envelope."""

    def test_business_error_envelope(self, client: TestClient, register_and_verify):
        """Duplicate registration triggers BusinessError → envelope."""
        register_and_verify("fmt_dup@example.com", "Pass1234")
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "fmt_dup@example.com", "password": "x"},
        )
        assert resp.status_code == 409
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.CONFLICT
        assert isinstance(body["message"], str)

    def test_validation_error_envelope(self, client: TestClient):
        """Missing required field triggers RequestValidationError → envelope."""
        resp = client.post("/api/v1/auth/register", json={})
        assert resp.status_code == 422
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.INVALID_PARAM
        assert isinstance(body["data"], list)

    def test_auth_middleware_unauthorized_envelope(self, client: TestClient):
        """No token on protected endpoint → envelope from middleware."""
        resp = client.get("/api/v1/user/whoami")
        assert resp.status_code == 401
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.UNAUTHORIZED

    def test_auth_middleware_invalid_token_envelope(self, client: TestClient):
        """Bad token on protected endpoint → envelope from middleware."""
        resp = client.get(
            "/api/v1/user/whoami",
            headers={"Authorization": "Bearer garbage"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.UNAUTHORIZED

    def test_login_wrong_password_envelope(self, client: TestClient, register_and_verify):
        """Wrong password → BusinessError → envelope."""
        register_and_verify("fmt_login@example.com", "Right123")
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "fmt_login@example.com", "password": "wrong"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.UNAUTHORIZED

    def test_refresh_invalid_token_envelope(self, client: TestClient):
        """Invalid refresh token → BusinessError → envelope."""
        resp = client.post(
            "/api/v1/auth/token/refresh",
            json={"refresh_token": "nonexistent"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.UNAUTHORIZED


class TestSuccessResponseFormat:
    """Success responses also use {code, message, data} envelope."""

    def test_register_success_envelope(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "fmt_ok@example.com", "password": "Pass1234"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.OK

    def test_login_success_envelope(self, client: TestClient, register_and_verify):
        register_and_verify("fmt_login_ok@example.com", "Pass1234")
        resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "fmt_login_ok@example.com", "password": "Pass1234"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.OK
        assert "access_token" in body["data"]
        assert "refresh_token" in body["data"]

    def test_whoami_success_envelope(self, client: TestClient, register_and_verify):
        data = register_and_verify("fmt_who@example.com", "Pass1234")
        resp = client.get(
            "/api/v1/user/whoami",
            headers={"Authorization": f"Bearer {data['data']['access_token']}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.OK
        assert "username" in body["data"]

    def test_root_endpoint_envelope(self, client: TestClient):
        resp = client.get("/api/v1/")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.OK
