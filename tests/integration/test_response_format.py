"""
Integration tests for response format stability.

Verifies that ALL responses (success and error) from the real app
follow the standardized envelope: {code, message, data}.
"""

from fastapi.testclient import TestClient

from common.resp import Code

ENVELOPE_KEYS = {"code", "message", "data"}


def register_and_verify(client: TestClient, email: str, password: str) -> dict:
    from auth.verification import _verification_codes

    client.post("/auth/register", json={"email": email, "password": password})
    key = f"{email.lower()}:register"
    code = _verification_codes[key].code
    response = client.post(
        "/auth/register/verify",
        json={"email": email, "code": code, "password": password},
    )
    return response.json()


class TestErrorResponseFormat:
    """All error responses must be HTTP 200 with {code, message, data} envelope."""

    def test_business_error_envelope(self, client: TestClient):
        """Duplicate registration triggers BusinessError → envelope."""
        register_and_verify(client, "fmt_dup@example.com", "pass")
        resp = client.post(
            "/auth/register",
            json={"email": "fmt_dup@example.com", "password": "x"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.CONFLICT
        assert isinstance(body["message"], str)

    def test_validation_error_envelope(self, client: TestClient):
        """Missing required field triggers RequestValidationError → envelope."""
        resp = client.post("/auth/register", json={})
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.INVALID_PARAM
        assert isinstance(body["data"], list)

    def test_auth_middleware_unauthorized_envelope(self, client: TestClient):
        """No token on protected endpoint → envelope from middleware."""
        resp = client.get("/user/whoami")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.UNAUTHORIZED

    def test_auth_middleware_invalid_token_envelope(self, client: TestClient):
        """Bad token on protected endpoint → envelope from middleware."""
        resp = client.get(
            "/user/whoami",
            headers={"Authorization": "Bearer garbage"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.UNAUTHORIZED

    def test_login_wrong_password_envelope(self, client: TestClient):
        """Wrong password → BusinessError → envelope."""
        register_and_verify(client, "fmt_login@example.com", "right")
        resp = client.post(
            "/auth/login",
            data={"username": "fmt_login@example.com", "password": "wrong"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.UNAUTHORIZED

    def test_refresh_invalid_token_envelope(self, client: TestClient):
        """Invalid refresh token → BusinessError → envelope."""
        resp = client.post(
            "/auth/token/refresh",
            json={"refresh_token": "nonexistent"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.UNAUTHORIZED


class TestSuccessResponseFormat:
    """Success responses also use {code, message, data} envelope."""

    def test_register_success_envelope(self, client: TestClient):
        resp = client.post(
            "/auth/register",
            json={"email": "fmt_ok@example.com", "password": "pass"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.OK

    def test_login_success_envelope(self, client: TestClient):
        register_and_verify(client, "fmt_login_ok@example.com", "pass")
        resp = client.post(
            "/auth/login",
            data={"username": "fmt_login_ok@example.com", "password": "pass"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.OK
        assert "access_token" in body["data"]
        assert "refresh_token" in body["data"]

    def test_whoami_success_envelope(self, client: TestClient):
        data = register_and_verify(client, "fmt_who@example.com", "pass")
        resp = client.get(
            "/user/whoami",
            headers={"Authorization": f"Bearer {data['data']['access_token']}"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.OK
        assert "username" in body["data"]

    def test_root_endpoint_envelope(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == ENVELOPE_KEYS
        assert body["code"] == Code.OK
