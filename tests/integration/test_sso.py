"""Integration tests for SSO endpoints."""

from fastapi.testclient import TestClient

from common.resp import Code


class TestSSOEndpoints:
    """Test SSO handler endpoints with validation."""

    def test_authorize_unsupported_provider(self, client: TestClient):
        resp = client.get("/api/v1/auth/twitter/authorize")
        assert resp.json()["code"] == Code.BAD_REQUEST

    def test_callback_unsupported_provider(self, client: TestClient):
        resp = client.get("/api/v1/auth/twitter/callback", params={"code": "x", "state": "y"})
        assert resp.json()["code"] == Code.BAD_REQUEST

    def test_callback_invalid_state(self, client: TestClient):
        resp = client.get("/api/v1/auth/google/callback", params={"code": "x", "state": "invalid"})
        assert resp.json()["code"] == Code.BAD_REQUEST

    def test_unlink_requires_auth(self, client: TestClient):
        resp = client.delete("/api/v1/auth/google/unlink")
        assert resp.status_code == 401

    def test_list_providers_requires_auth(self, client: TestClient):
        resp = client.get("/api/v1/auth/providers")
        assert resp.status_code == 401

    def test_list_providers_authenticated(self, client: TestClient, auth_header):
        headers = auth_header("sso@example.com", "Pass1234")
        resp = client.get("/api/v1/auth/providers", headers=headers)
        assert resp.json()["code"] == Code.OK
        data = resp.json()["data"]
        assert data["providers"] == []
        assert data["has_password"] is True

    def test_unlink_not_linked(self, client: TestClient, auth_header):
        headers = auth_header("unlink@example.com", "Pass1234")
        resp = client.delete("/api/v1/auth/google/unlink", headers=headers)
        assert resp.json()["code"] == Code.NOT_FOUND
