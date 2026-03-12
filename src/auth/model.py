from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from conf.db import AsyncSessionLocal, Base


class InvitationCode(Base):
    __tablename__ = "invitation_code"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    max_uses: Mapped[int] = mapped_column(default=0)  # 0 means unlimited
    used_count: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


async def get_invitation_code(code: str) -> InvitationCode | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(InvitationCode).where(InvitationCode.code == code))
        return result.scalars().one_or_none()


async def validate_invitation_code(code: str) -> InvitationCode | None:
    """Return the invitation code if valid, None otherwise."""
    invitation = await get_invitation_code(code)
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


async def increment_used_count(code_id: UUID) -> bool:
    async with AsyncSessionLocal() as session:
        invitation = await session.get(InvitationCode, code_id)
        if not invitation:
            return False
        invitation.used_count += 1
        session.add(invitation)
        await session.commit()
        return True
