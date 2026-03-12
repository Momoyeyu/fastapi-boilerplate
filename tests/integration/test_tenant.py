"""Integration tests for tenant CRUD and registration-creates-tenant flow."""

from fastapi.testclient import TestClient

from common.resp import Code


class TestRegistrationCreatesTenant:
    """Verify that registration creates a default tenant."""

    def test_register_creates_default_tenant(self, client: TestClient, auth_header):
        """After registration, user should have a default tenant as owner."""
        headers = auth_header("tenantuser@example.com", "Pass1234")

        # List tenants
        resp = client.get("/api/v1/tenant", headers=headers)
        assert resp.json()["code"] == Code.OK
        tenants = resp.json()["data"]
        assert len(tenants) >= 1

        # First tenant should be the auto-created one
        t = tenants[0]
        assert t["user_role"] == "owner"
        assert t["tenant_name"].startswith("workspace_")


class TestTenantCRUD:
    """Tests for tenant create, read, update, list endpoints."""

    def test_create_tenant(self, client: TestClient, auth_header):
        headers = auth_header("creator@example.com", "Pass1234")
        resp = client.post(
            "/api/v1/tenant",
            headers=headers,
            json={"name": "My New Org"},
        )
        assert resp.json()["code"] == Code.OK
        data = resp.json()["data"]
        assert data["name"] == "My New Org"
        assert data["status"] == "active"

    def test_get_tenant(self, client: TestClient, auth_header):
        headers = auth_header("getter@example.com", "Pass1234")

        # Create a tenant first
        create_resp = client.post("/api/v1/tenant", headers=headers, json={"name": "Getter Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # Get it
        resp = client.get(f"/api/v1/tenant/{tenant_id}", headers=headers)
        assert resp.json()["code"] == Code.OK
        assert resp.json()["data"]["name"] == "Getter Org"

    def test_list_tenants(self, client: TestClient, auth_header):
        headers = auth_header("lister@example.com", "Pass1234")

        # Create extra tenants
        client.post("/api/v1/tenant", headers=headers, json={"name": "Org A"})
        client.post("/api/v1/tenant", headers=headers, json={"name": "Org B"})

        resp = client.get("/api/v1/tenant", headers=headers)
        assert resp.json()["code"] == Code.OK
        # Default tenant + 2 created = 3
        assert len(resp.json()["data"]) >= 3

    def test_update_tenant_as_owner(self, client: TestClient, auth_header):
        headers = auth_header("owner@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=headers, json={"name": "Update Me"})
        tenant_id = create_resp.json()["data"]["id"]

        resp = client.put(
            f"/api/v1/tenant/{tenant_id}",
            headers=headers,
            json={"name": "Updated Name"},
        )
        assert resp.json()["code"] == Code.OK
        assert resp.json()["data"]["name"] == "Updated Name"

    def test_get_tenant_not_member(self, client: TestClient, auth_header):
        """User should not access a tenant they don't belong to."""
        headers_a = auth_header("usera@example.com", "Pass1234")
        headers_b = auth_header("userb@example.com", "Pass1234")

        # A creates a tenant
        create_resp = client.post("/api/v1/tenant", headers=headers_a, json={"name": "Private Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # B tries to access it
        resp = client.get(f"/api/v1/tenant/{tenant_id}", headers=headers_b)
        assert resp.json()["code"] == Code.NOT_FOUND
