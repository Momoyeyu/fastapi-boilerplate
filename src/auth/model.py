import secrets
from datetime import UTC, datetime, timedelta

from sqlmodel import Field, Session, SQLModel, select

from conf.config import settings
from conf.db import engine


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"

    id: int | None = Field(default=None, primary_key=True)
    token: str = Field(unique=True, index=True)
    user_id: int = Field(index=True)
    username: str
    expires_at: datetime
    revoked: bool = Field(default=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def generate_refresh_token() -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(32)


def create_refresh_token(user_id: int, username: str) -> RefreshToken:
    """Create and store a new refresh token for the user."""
    token = generate_refresh_token()
    expires_at = datetime.now(UTC) + timedelta(seconds=settings.refresh_token_expire_seconds)

    refresh_token = RefreshToken(
        token=token,
        user_id=user_id,
        username=username,
        expires_at=expires_at,
    )

    with Session(engine) as session:
        session.add(refresh_token)
        session.commit()
        session.refresh(refresh_token)

    return refresh_token


def get_refresh_token(token: str) -> RefreshToken | None:
    """Get a refresh token by its token string."""
    with Session(engine) as session:
        return session.exec(select(RefreshToken).where(RefreshToken.token == token)).one_or_none()


def validate_refresh_token(token: str) -> RefreshToken | None:
    """Validate a refresh token and return it if valid.

    Returns None if the token is invalid, expired, or revoked.
    """
    refresh_token = get_refresh_token(token)
    if not refresh_token:
        return None

    if refresh_token.revoked:
        return None

    # Check expiration (ensure both datetimes are timezone-aware for comparison)
    now = datetime.now(UTC)
    expires_at = (
        refresh_token.expires_at.replace(tzinfo=UTC)
        if refresh_token.expires_at.tzinfo is None
        else refresh_token.expires_at
    )
    if expires_at < now:
        return None

    return refresh_token


def revoke_refresh_token(token: str) -> bool:
    """Revoke a refresh token.

    Returns True if the token was found and revoked, False otherwise.
    """
    with Session(engine) as session:
        refresh_token = session.exec(select(RefreshToken).where(RefreshToken.token == token)).one_or_none()

        if not refresh_token:
            return False

        refresh_token.revoked = True
        session.add(refresh_token)
        session.commit()

    return True


def revoke_all_user_tokens(user_id: int) -> int:
    """Revoke all refresh tokens for a user.

    Returns the number of tokens revoked.
    """
    with Session(engine) as session:
        tokens = session.exec(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,  # noqa: E712
            )
        ).all()

        count = 0
        for token in tokens:
            token.revoked = True
            session.add(token)
            count += 1

        session.commit()

    return count


def rotate_refresh_token(old_token: str) -> RefreshToken | None:
    """Atomically rotate a refresh token.

    Validates, revokes the old token, and creates a new one in a single transaction.
    Returns None if the old token is invalid/expired/revoked.
    """
    with Session(engine) as session:
        # Query within the transaction
        token_obj = session.exec(select(RefreshToken).where(RefreshToken.token == old_token)).one_or_none()

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

        session.commit()
        session.refresh(new_refresh_token)

        return new_refresh_token
