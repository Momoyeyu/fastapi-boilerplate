from datetime import UTC, datetime, timedelta

import pytest

import invitation.model as inv_model
from invitation.model import InvitationCode


@pytest.fixture
def _patch_get(monkeypatch: pytest.MonkeyPatch):
    """Helper to set what get_invitation_code returns."""

    def _set(code: InvitationCode | None):
        monkeypatch.setattr(inv_model, "get_invitation_code", lambda c: code)

    return _set


def test_validate_not_found(_patch_get):
    _patch_get(None)
    assert inv_model.validate_invitation_code("NOPE") is None


def test_validate_inactive(_patch_get):
    inv = InvitationCode(id=1, code="X", is_active=False)
    _patch_get(inv)
    assert inv_model.validate_invitation_code("X") is None


def test_validate_expired(_patch_get):
    inv = InvitationCode(id=1, code="X", is_active=True, expires_at=datetime.now(UTC) - timedelta(hours=1))
    _patch_get(inv)
    assert inv_model.validate_invitation_code("X") is None


def test_validate_max_uses_reached(_patch_get):
    inv = InvitationCode(id=1, code="X", is_active=True, max_uses=5, used_count=5)
    _patch_get(inv)
    assert inv_model.validate_invitation_code("X") is None


def test_validate_unlimited_uses(_patch_get):
    inv = InvitationCode(id=1, code="X", is_active=True, max_uses=0, used_count=999)
    _patch_get(inv)
    result = inv_model.validate_invitation_code("X")
    assert result is not None
    assert result.code == "X"


def test_validate_valid_code(_patch_get):
    inv = InvitationCode(
        id=1,
        code="VALID",
        is_active=True,
        max_uses=10,
        used_count=3,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    _patch_get(inv)
    result = inv_model.validate_invitation_code("VALID")
    assert result is not None
    assert result.id == 1
