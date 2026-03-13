"""Integration tests for tenant invitation feature."""

from fastapi.testclient import TestClient
from sqlalchemy import select

from common.resp import Code
from tenant.model import TenantInvitation


class TestTenantInviteExistingUser:
    """Inviting an already-registered user adds them to the tenant directly."""

    def test_invite_existing_user(self, client: TestClient, auth_header, register_and_verify, mock_email):
        headers_a = auth_header("owner@example.com", "Pass1234")
        register_and_verify("invitee@example.com", "Pass1234")

        # Owner creates a tenant
        create_resp = client.post("/api/v1/tenant", headers=headers_a, json={"name": "Invite Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # Invite existing user
        resp = client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers_a,
            json={"email": "invitee@example.com", "role": "member"},
        )
        assert resp.json()["code"] == Code.OK
        assert resp.json()["data"]["flow"] == "existing_user"

        # Verify invitee can see the tenant — re-login
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "invitee@example.com", "password": "Pass1234"},
        )
        invitee_headers = {"Authorization": f"Bearer {login_resp.json()['data']['access_token']}"}

        tenants_resp = client.get("/api/v1/tenant", headers=invitee_headers)
        tenant_names = [t["tenant_name"] for t in tenants_resp.json()["data"]]
        assert "Invite Org" in tenant_names

    def test_invite_existing_user_already_member(self, client: TestClient, auth_header, register_and_verify):
        headers_a = auth_header("ownerdup@example.com", "Pass1234")
        register_and_verify("dupuser@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=headers_a, json={"name": "Dup Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # First invite succeeds
        resp1 = client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers_a,
            json={"email": "dupuser@example.com", "role": "member"},
        )
        assert resp1.json()["code"] == Code.OK

        # Second invite should conflict
        resp2 = client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers_a,
            json={"email": "dupuser@example.com", "role": "member"},
        )
        assert resp2.json()["code"] == Code.CONFLICT


class TestTenantInviteNewUser:
    """Inviting a new (unregistered) email creates a pending invitation."""

    def test_invite_new_user_and_accept(self, client: TestClient, auth_header, session, mock_email):
        headers = auth_header("host@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=headers, json={"name": "New User Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # Invite a new email
        resp = client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers,
            json={"email": "newcomer@example.com", "role": "admin"},
        )
        assert resp.json()["code"] == Code.OK
        assert resp.json()["data"]["flow"] == "new_user"

        # Verify invitation appears in list
        list_resp = client.get(f"/api/v1/tenant/{tenant_id}/invitations", headers=headers)
        assert list_resp.json()["code"] == Code.OK
        invitations = list_resp.json()["data"]
        assert len(invitations) == 1
        assert invitations[0]["email"] == "newcomer@example.com"
        assert invitations[0]["role"] == "admin"

    def test_accept_invitation(self, client: TestClient, auth_header, session):
        headers = auth_header("host2@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=headers, json={"name": "Accept Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # Invite
        client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers,
            json={"email": "accepter@example.com", "role": "member"},
        )

        # Token is not in the list response for security, so get it from DB
        import asyncio

        async def get_token():
            async with session.begin():
                result = await session.execute(
                    select(TenantInvitation).where(TenantInvitation.email == "accepter@example.com")
                )
                inv = result.scalars().one()
                return inv.token

        token = asyncio.get_event_loop().run_until_complete(get_token())

        # Accept the invitation
        accept_resp = client.post(
            "/api/v1/auth/invite/accept",
            json={"token": token, "password": "NewPass1234"},
        )
        assert accept_resp.json()["code"] == Code.OK
        assert "access_token" in accept_resp.json()["data"]

        # Use the new token to verify tenant membership
        new_headers = {"Authorization": f"Bearer {accept_resp.json()['data']['access_token']}"}
        tenants_resp = client.get("/api/v1/tenant", headers=new_headers)
        tenant_names = [t["tenant_name"] for t in tenants_resp.json()["data"]]
        assert "Accept Org" in tenant_names

    def test_duplicate_pending_invitation(self, client: TestClient, auth_header):
        headers = auth_header("host3@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=headers, json={"name": "Dup Invite Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # First invite
        resp1 = client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers,
            json={"email": "pending@example.com", "role": "member"},
        )
        assert resp1.json()["code"] == Code.OK

        # Second invite for same email should conflict
        resp2 = client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers,
            json={"email": "pending@example.com", "role": "admin"},
        )
        assert resp2.json()["code"] == Code.CONFLICT


class TestTenantInvitePermissions:
    """Permission checks for invitation endpoints."""

    def test_member_cannot_invite(self, client: TestClient, auth_header, register_and_verify):
        """A regular member should not be able to invite."""
        owner_headers = auth_header("permowner@example.com", "Pass1234")
        register_and_verify("permmember@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=owner_headers, json={"name": "Perm Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # Add member
        client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=owner_headers,
            json={"email": "permmember@example.com", "role": "member"},
        )

        # Member tries to invite
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "permmember@example.com", "password": "Pass1234"},
        )
        member_headers = {"Authorization": f"Bearer {login_resp.json()['data']['access_token']}"}

        resp = client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=member_headers,
            json={"email": "someone@example.com", "role": "member"},
        )
        assert resp.json()["code"] == Code.FORBIDDEN

    def test_non_member_cannot_invite(self, client: TestClient, auth_header):
        """A user not in the tenant should get not_found."""
        owner_headers = auth_header("nmowner@example.com", "Pass1234")
        other_headers = auth_header("nmother@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=owner_headers, json={"name": "NM Org"})
        tenant_id = create_resp.json()["data"]["id"]

        resp = client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=other_headers,
            json={"email": "someone@example.com", "role": "member"},
        )
        assert resp.json()["code"] == Code.NOT_FOUND

    def test_member_cannot_list_invitations(self, client: TestClient, auth_header, register_and_verify):
        """A regular member should not be able to list invitations."""
        owner_headers = auth_header("listowner@example.com", "Pass1234")
        register_and_verify("listmember@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=owner_headers, json={"name": "List Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # Add member
        client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=owner_headers,
            json={"email": "listmember@example.com", "role": "member"},
        )

        login_resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "listmember@example.com", "password": "Pass1234"},
        )
        member_headers = {"Authorization": f"Bearer {login_resp.json()['data']['access_token']}"}

        resp = client.get(f"/api/v1/tenant/{tenant_id}/invitations", headers=member_headers)
        assert resp.json()["code"] == Code.FORBIDDEN


class TestTenantInviteCancellation:
    """Tests for cancelling invitations."""

    def test_cancel_pending_invitation(self, client: TestClient, auth_header, session):
        headers = auth_header("cancelhost@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=headers, json={"name": "Cancel Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # Invite a new user
        client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers,
            json={"email": "cancelled@example.com", "role": "member"},
        )

        # Get invitation id from list
        list_resp = client.get(f"/api/v1/tenant/{tenant_id}/invitations", headers=headers)
        invitation_id = list_resp.json()["data"][0]["id"]

        # Cancel the invitation
        resp = client.delete(f"/api/v1/tenant/{tenant_id}/invitations/{invitation_id}", headers=headers)
        assert resp.json()["code"] == Code.OK

        # Verify it no longer appears in pending list
        list_resp2 = client.get(f"/api/v1/tenant/{tenant_id}/invitations", headers=headers)
        assert len(list_resp2.json()["data"]) == 0

    def test_member_cannot_cancel(self, client: TestClient, auth_header, register_and_verify):
        owner_headers = auth_header("cancelowner@example.com", "Pass1234")
        register_and_verify("cancelmember@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=owner_headers, json={"name": "Cancel Perm Org"})
        tenant_id = create_resp.json()["data"]["id"]

        # Add member
        client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=owner_headers,
            json={"email": "cancelmember@example.com", "role": "member"},
        )

        # Invite someone else
        client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=owner_headers,
            json={"email": "target@example.com", "role": "member"},
        )

        list_resp = client.get(f"/api/v1/tenant/{tenant_id}/invitations", headers=owner_headers)
        invitation_id = list_resp.json()["data"][0]["id"]

        # Member tries to cancel
        login_resp = client.post(
            "/api/v1/auth/login",
            json={"identifier": "cancelmember@example.com", "password": "Pass1234"},
        )
        member_headers = {"Authorization": f"Bearer {login_resp.json()['data']['access_token']}"}

        resp = client.delete(f"/api/v1/tenant/{tenant_id}/invitations/{invitation_id}", headers=member_headers)
        assert resp.json()["code"] == Code.FORBIDDEN

    def test_cancel_nonexistent_invitation(self, client: TestClient, auth_header):
        headers = auth_header("cancelmiss@example.com", "Pass1234")
        create_resp = client.post("/api/v1/tenant", headers=headers, json={"name": "Cancel Miss Org"})
        tenant_id = create_resp.json()["data"]["id"]

        fake_id = "019cdc15-79f5-7097-9939-415ca4826de7"
        resp = client.delete(f"/api/v1/tenant/{tenant_id}/invitations/{fake_id}", headers=headers)
        assert resp.json()["code"] == Code.NOT_FOUND

    def test_cancel_already_cancelled(self, client: TestClient, auth_header):
        headers = auth_header("canceltwice@example.com", "Pass1234")
        create_resp = client.post("/api/v1/tenant", headers=headers, json={"name": "Cancel Twice Org"})
        tenant_id = create_resp.json()["data"]["id"]

        client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers,
            json={"email": "canceltwice_target@example.com", "role": "member"},
        )

        list_resp = client.get(f"/api/v1/tenant/{tenant_id}/invitations", headers=headers)
        invitation_id = list_resp.json()["data"][0]["id"]

        # First cancel succeeds
        resp1 = client.delete(f"/api/v1/tenant/{tenant_id}/invitations/{invitation_id}", headers=headers)
        assert resp1.json()["code"] == Code.OK

        # Second cancel fails
        resp2 = client.delete(f"/api/v1/tenant/{tenant_id}/invitations/{invitation_id}", headers=headers)
        assert resp2.json()["code"] == Code.BAD_REQUEST


class TestTenantInviteAcceptEdgeCases:
    """Edge cases for accepting invitations."""

    def test_accept_invalid_token(self, client: TestClient):
        resp = client.post(
            "/api/v1/auth/invite/accept",
            json={"token": "nonexistent-token", "password": "StrongPw1"},
        )
        assert resp.json()["code"] == Code.BAD_REQUEST

    def test_accept_same_token_twice(self, client: TestClient, auth_header, session):
        headers = auth_header("twicehost@example.com", "Pass1234")

        create_resp = client.post("/api/v1/tenant", headers=headers, json={"name": "Twice Org"})
        tenant_id = create_resp.json()["data"]["id"]

        client.post(
            f"/api/v1/tenant/{tenant_id}/invite",
            headers=headers,
            json={"email": "twice@example.com", "role": "member"},
        )

        import asyncio

        async def get_token():
            async with session.begin():
                result = await session.execute(
                    select(TenantInvitation).where(TenantInvitation.email == "twice@example.com")
                )
                inv = result.scalars().one()
                return inv.token

        token = asyncio.get_event_loop().run_until_complete(get_token())

        # First accept succeeds
        resp1 = client.post(
            "/api/v1/auth/invite/accept",
            json={"token": token, "password": "StrongPw1"},
        )
        assert resp1.json()["code"] == Code.OK

        # Second accept fails (token already consumed)
        resp2 = client.post(
            "/api/v1/auth/invite/accept",
            json={"token": token, "password": "StrongPw1"},
        )
        assert resp2.json()["code"] == Code.BAD_REQUEST
