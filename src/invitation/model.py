from datetime import UTC, datetime

from sqlmodel import Field, Session, SQLModel, select

from conf.db import engine


class InvitationCode(SQLModel, table=True):
    __tablename__ = "invitation_code"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True, max_length=50)
    max_uses: int = Field(default=0)  # 0 means unlimited
    used_count: int = Field(default=0)
    is_active: bool = Field(default=True)
    expires_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def get_invitation_code(code: str) -> InvitationCode | None:
    with Session(engine) as session:
        return session.exec(select(InvitationCode).where(InvitationCode.code == code)).one_or_none()


def validate_invitation_code(code: str) -> InvitationCode | None:
    """Return the invitation code if valid, None otherwise."""
    invitation = get_invitation_code(code)
    if not invitation or not invitation.is_active:
        return None
    if invitation.expires_at is not None:
        now = datetime.now(UTC)
        expires_at = (
            invitation.expires_at.replace(tzinfo=UTC) if invitation.expires_at.tzinfo is None else invitation.expires_at
        )
        if expires_at < now:
            return None
    if invitation.max_uses > 0 and invitation.used_count >= invitation.max_uses:
        return None
    return invitation


def increment_used_count(code_id: int) -> bool:
    with Session(engine) as session:
        invitation = session.get(InvitationCode, code_id)
        if not invitation:
            return False
        invitation.used_count += 1
        session.add(invitation)
        session.commit()
        return True
