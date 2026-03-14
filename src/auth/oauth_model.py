from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from conf.db import AsyncSessionLocal, Base


class OAuthAccount(Base):
    __tablename__ = "oauth_account"
    __table_args__ = (UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("user.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(50))
    provider_user_id: Mapped[str] = mapped_column(String(255))
    provider_email: Mapped[str | None] = mapped_column(String(255), default=None)
    provider_username: Mapped[str | None] = mapped_column(String(255), default=None)
    avatar_url: Mapped[str | None] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


async def get_oauth_account(provider: str, provider_user_id: str) -> OAuthAccount | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OAuthAccount).where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        return result.scalars().one_or_none()


async def get_oauth_accounts_for_user(user_id: UUID) -> list[OAuthAccount]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OAuthAccount).where(OAuthAccount.user_id == user_id))
        return list(result.scalars().all())


async def create_oauth_account(
    user_id: UUID,
    provider: str,
    provider_user_id: str,
    *,
    provider_email: str | None = None,
    provider_username: str | None = None,
    avatar_url: str | None = None,
) -> OAuthAccount:
    account = OAuthAccount(
        user_id=user_id,
        provider=provider,
        provider_user_id=provider_user_id,
        provider_email=provider_email,
        provider_username=provider_username,
        avatar_url=avatar_url,
    )
    async with AsyncSessionLocal() as session:
        session.add(account)
        await session.commit()
        await session.refresh(account)
    return account


async def delete_oauth_account(user_id: UUID, provider: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(OAuthAccount).where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == provider,
            )
        )
        account = result.scalars().one_or_none()
        if not account:
            return False
        await session.delete(account)
        await session.commit()
    return True
