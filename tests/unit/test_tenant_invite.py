from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from auth.token import TokenPair
from common import erri
from common.resp import Code
from tenant import invite
from tenant.model import TenantInvitation, UserTenant
from user.model import User

_INVITER_ID = UUID("01936b2a-7c00-7000-8000-000000000001")
_TENANT_ID = UUID("01936b2a-7c00-7000-8000-000000000002")
_USER_ID = UUID("01936b2a-7c00-7000-8000-000000000003")
_INVITATION_ID = UUID("01936b2a-7c00-7000-8000-000000000004")


def async_return(value):
    async def _inner(*args, **kwargs):
        return value

    return _inner


def _make_user_tenant(role: str) -> UserTenant:
    ut = MagicMock(spec=UserTenant)
    ut.user_role = role
    ut.user_id = _INVITER_ID
    ut.tenant_id = _TENANT_ID
    return ut


def _make_tenant() -> MagicMock:
    t = MagicMock()
    t.id = _TENANT_ID
    t.name = "Test Tenant"
    t.status = "active"
    return t


def _make_user(email: str = "existing@test.com") -> User:
    u = MagicMock(spec=User)
    u.id = _USER_ID
    u.username = email.split("@")[0]
    u.email = email
    return u


def _make_invitation(*, expired: bool = False) -> TenantInvitation:
    inv = MagicMock(spec=TenantInvitation)
    inv.id = _INVITATION_ID
    inv.tenant_id = _TENANT_ID
    inv.email = "new@test.com"
    inv.role = "member"
    inv.invited_by = _INVITER_ID
    inv.token = "test-token"
    inv.status = "pending"
    if expired:
        inv.expires_at = datetime.now(UTC) - timedelta(hours=1)
    else:
        inv.expires_at = datetime.now(UTC) + timedelta(days=7)
    return inv


@pytest.fixture
def mock_settings(monkeypatch):
    mock = MagicMock()
    mock.invitation_token_expire_seconds = 604800
    mock.frontend_url = "http://localhost:3000"
    mock.app_name = "Test"
    monkeypatch.setattr(invite, "settings", mock)
    return mock


# ---------------------------------------------------------------------------
# invite_user_to_tenant
# ---------------------------------------------------------------------------


class TestInviteUserToTenant:
    async def test_invalid_role(self, monkeypatch):
        monkeypatch.setattr(invite, "get_user_tenant", async_return(_make_user_tenant("owner")))
        with pytest.raises(erri.BusinessError) as exc:
            await invite.invite_user_to_tenant(_INVITER_ID, _TENANT_ID, "a@test.com", "superadmin")
        assert exc.value.code == Code.BAD_REQUEST

    async def test_inviter_not_member(self, monkeypatch):
        monkeypatch.setattr(invite, "get_user_tenant", async_return(None))
        with pytest.raises(erri.BusinessError) as exc:
            await invite.invite_user_to_tenant(_INVITER_ID, _TENANT_ID, "a@test.com", "member")
        assert exc.value.code == Code.NOT_FOUND

    async def test_inviter_not_owner_or_admin(self, monkeypatch):
        monkeypatch.setattr(invite, "get_user_tenant", async_return(_make_user_tenant("member")))
        with pytest.raises(erri.BusinessError) as exc:
            await invite.invite_user_to_tenant(_INVITER_ID, _TENANT_ID, "a@test.com", "member")
        assert exc.value.code == Code.FORBIDDEN

    async def test_tenant_not_found(self, monkeypatch):
        monkeypatch.setattr(invite, "get_user_tenant", async_return(_make_user_tenant("owner")))
        monkeypatch.setattr(invite, "get_tenant", async_return(None))
        with pytest.raises(erri.BusinessError) as exc:
            await invite.invite_user_to_tenant(_INVITER_ID, _TENANT_ID, "a@test.com", "member")
        assert exc.value.code == Code.NOT_FOUND

    async def test_duplicate_pending_invitation(self, monkeypatch):
        monkeypatch.setattr(invite, "get_user_tenant", async_return(_make_user_tenant("owner")))
        monkeypatch.setattr(invite, "get_tenant", async_return(_make_tenant()))
        monkeypatch.setattr(invite, "get_pending_invitation_by_email_and_tenant", async_return(_make_invitation()))
        with pytest.raises(erri.BusinessError) as exc:
            await invite.invite_user_to_tenant(_INVITER_ID, _TENANT_ID, "new@test.com", "member")
        assert exc.value.code == Code.CONFLICT

    async def test_existing_user_already_member(self, monkeypatch):
        user = _make_user()
        ut = _make_user_tenant("member")

        call_count = {"n": 0}

        async def side_effect_get_user_tenant(uid, tid):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _make_user_tenant("owner")  # inviter check
            return ut  # existing user membership check

        monkeypatch.setattr(invite, "get_user_tenant", side_effect_get_user_tenant)
        monkeypatch.setattr(invite, "get_tenant", async_return(_make_tenant()))
        monkeypatch.setattr(invite, "get_pending_invitation_by_email_and_tenant", async_return(None))
        monkeypatch.setattr(invite, "get_user_by_email", async_return(user))

        with pytest.raises(erri.BusinessError) as exc:
            await invite.invite_user_to_tenant(_INVITER_ID, _TENANT_ID, "existing@test.com", "member")
        assert exc.value.code == Code.CONFLICT

    async def test_existing_user_success(self, monkeypatch):
        user = _make_user()

        call_count = {"n": 0}

        async def side_effect_get_user_tenant(uid, tid):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _make_user_tenant("owner")  # inviter check
            return None  # existing user not yet member

        monkeypatch.setattr(invite, "get_user_tenant", side_effect_get_user_tenant)
        monkeypatch.setattr(invite, "get_tenant", async_return(_make_tenant()))
        monkeypatch.setattr(invite, "get_pending_invitation_by_email_and_tenant", async_return(None))
        monkeypatch.setattr(invite, "get_user_by_email", async_return(user))
        monkeypatch.setattr(invite, "create_user_tenant", async_return(_make_user_tenant("member")))
        monkeypatch.setattr(invite, "_send_added_email", async_return(True))

        result = await invite.invite_user_to_tenant(_INVITER_ID, _TENANT_ID, "existing@test.com", "member")
        assert result["flow"] == "existing_user"

    async def test_new_user_success(self, monkeypatch, mock_settings):
        monkeypatch.setattr(invite, "get_user_tenant", async_return(_make_user_tenant("admin")))
        monkeypatch.setattr(invite, "get_tenant", async_return(_make_tenant()))
        monkeypatch.setattr(invite, "get_pending_invitation_by_email_and_tenant", async_return(None))
        monkeypatch.setattr(invite, "get_user_by_email", async_return(None))
        monkeypatch.setattr(invite, "create_tenant_invitation", async_return(_make_invitation()))
        monkeypatch.setattr(invite, "_send_invite_email", async_return(True))

        result = await invite.invite_user_to_tenant(_INVITER_ID, _TENANT_ID, "new@test.com", "member")
        assert result["flow"] == "new_user"


# ---------------------------------------------------------------------------
# accept_invitation
# ---------------------------------------------------------------------------


class TestAcceptInvitation:
    async def test_invalid_token(self, monkeypatch):
        monkeypatch.setattr(invite, "get_invitation_by_token", async_return(None))
        with pytest.raises(erri.BusinessError) as exc:
            await invite.accept_invitation("bad-token", "StrongPw1")
        assert exc.value.code == Code.BAD_REQUEST

    async def test_expired_token(self, monkeypatch):
        monkeypatch.setattr(invite, "get_invitation_by_token", async_return(_make_invitation(expired=True)))
        with pytest.raises(erri.BusinessError) as exc:
            await invite.accept_invitation("expired-token", "StrongPw1")
        assert exc.value.code == Code.BAD_REQUEST

    async def test_email_already_registered(self, monkeypatch):
        monkeypatch.setattr(invite, "get_invitation_by_token", async_return(_make_invitation()))
        monkeypatch.setattr(invite, "email_exists", async_return(True))
        with pytest.raises(erri.BusinessError) as exc:
            await invite.accept_invitation("valid-token", "StrongPw1")
        assert exc.value.code == Code.CONFLICT

    async def test_weak_password(self, monkeypatch):
        monkeypatch.setattr(invite, "get_invitation_by_token", async_return(_make_invitation()))
        monkeypatch.setattr(invite, "email_exists", async_return(False))

        def strict_validate(pw):
            raise erri.bad_request("Password too weak")

        monkeypatch.setattr(invite, "validate_password", strict_validate)
        with pytest.raises(erri.BusinessError) as exc:
            await invite.accept_invitation("valid-token", "weak")
        assert exc.value.code == Code.BAD_REQUEST

    async def test_success(self, monkeypatch):
        inv = _make_invitation()
        user = _make_user("new@test.com")
        token_pair = TokenPair(access_token="at", refresh_token="rt", expires_in=3600, refresh_token_expires_in=604800)

        monkeypatch.setattr(invite, "get_invitation_by_token", async_return(inv))
        monkeypatch.setattr(invite, "email_exists", async_return(False))
        monkeypatch.setattr(invite, "validate_password", lambda pw: None)
        monkeypatch.setattr(invite, "get_password_hash", lambda pw: "hashed")
        monkeypatch.setattr(invite, "create_user_for_tenant", async_return((user, _make_user_tenant("member"))))
        monkeypatch.setattr(invite, "update_invitation_status", async_return(inv))
        monkeypatch.setattr(invite, "create_token", lambda u: token_pair)

        result = await invite.accept_invitation("valid-token", "StrongPw1")
        assert result.access_token == "at"
        assert result.refresh_token == "rt"
