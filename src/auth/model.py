import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from conf.config import settings
from conf.db import AsyncSessionLocal, Base


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String, unique=True, index=True)
    user_id: Mapped[int] = mapped_column(index=True)
    username: Mapped[str] = mapped_column(String)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


def generate_refresh_token() -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(32)


async def create_refresh_token(user_id: int, username: str) -> RefreshToken:
    """Create and store a new refresh token for the user."""
    token = generate_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.refresh_token_expire_seconds)

    refresh_token = RefreshToken(
        token=token,
        user_id=user_id,
        username=username,
        expires_at=expires_at,
    )

    async with AsyncSessionLocal() as session:
        session.add(refresh_token)
        await session.commit()
        await session.refresh(refresh_token)

    return refresh_token


async def revoke_refresh_token(token: str) -> bool:
    """Revoke a refresh token.

    Returns True if the token was found and revoked, False otherwise.
    """
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(RefreshToken).where(RefreshToken.token == token))
        refresh_token = result.scalars().one_or_none()

        if not refresh_token:
            return False

        refresh_token.revoked = True
        session.add(refresh_token)
        await session.commit()

    return True


async def rotate_refresh_token(old_token: str) -> RefreshToken | None:
    """Atomically rotate a refresh token.

    Validates, revokes the old token, and creates a new one in a single transaction.
    Returns None if the old token is invalid/expired/revoked.
    """
    async with AsyncSessionLocal() as session:
        # Query within the transaction
        result = await session.execute(select(RefreshToken).where(RefreshToken.token == old_token))
        token_obj = result.scalars().one_or_none()

        if not token_obj or token_obj.revoked:
            return None

        now = datetime.now(UTC)
        # Ensure both datetimes are timezone-aware for comparison
        expires_at = (
            token_obj.expires_at.replace(tzinfo=UTC) if token_obj.expires_at.tzinfo is None else token_obj.expires_at
        )
        if expires_at < now:
            return None

        # Revoke old token
        token_obj.revoked = True
        session.add(token_obj)

        # Create new token
        new_token = generate_refresh_token()
        expires_at = now + timedelta(seconds=settings.refresh_token_expire_seconds)
        new_refresh_token = RefreshToken(
            token=new_token,
            user_id=token_obj.user_id,
            username=token_obj.username,
            expires_at=expires_at,
        )
        session.add(new_refresh_token)

        await session.commit()
        await session.refresh(new_refresh_token)

        return new_refresh_token
