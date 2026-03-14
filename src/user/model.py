from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Uuid, select
from sqlalchemy.orm import Mapped, mapped_column
from uuid6 import uuid7

from conf.db import AsyncSessionLocal, Base


class User(Base):
    __tablename__ = "user"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid7)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str | None] = mapped_column(String, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String, default=None)
    is_active: Mapped[bool] = mapped_column(default=True)
    invitation_code_id: Mapped[UUID | None] = mapped_column(Uuid, default=None)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(UTC))


async def create_user(
    username: str,
    hashed_password: str,
    email: str,
    *,
    invitation_code_id: UUID | None = None,
) -> User | None:
    user = User(
        username=username,
        hashed_password=hashed_password,
        email=email,
        invitation_code_id=invitation_code_id,
    )
    async with AsyncSessionLocal() as session:
        try:
            session.add(user)
            await session.commit()
            await session.refresh(user)
        except Exception:
            await session.rollback()
            return None
    return user


async def get_user(username: str) -> User | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == username, User.is_deleted == False)  # noqa: E712
        )
        return result.scalars().one_or_none()


async def get_user_by_email(email: str) -> User | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == email.lower(), User.is_deleted == False)  # noqa: E712
        )
        return result.scalars().one_or_none()


async def get_user_by_id(user_id: UUID) -> User | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.id == user_id, User.is_deleted == False)  # noqa: E712
        )
        return result.scalars().one_or_none()


async def get_user_by_identifier(identifier: str) -> User | None:
    if "@" in identifier:
        return await get_user_by_email(identifier)
    return await get_user(identifier)


async def email_exists(email: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.email == email.lower(), User.is_deleted == False)  # noqa: E712
        )
        return result.scalars().one_or_none() is not None


async def update_user_profile(
    username: str,
    *,
    new_username: str | None = None,
    email: str | None = None,
    avatar_url: str | None = None,
) -> User | None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == username, User.is_deleted == False)  # noqa: E712
        )
        user = result.scalars().one_or_none()
        if not user:
            return None

        if new_username is not None:
            user.username = new_username
        if email is not None:
            user.email = email.lower()
        if avatar_url is not None:
            user.avatar_url = avatar_url

        user.updated_at = datetime.now(UTC)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


async def update_user_password(username: str, new_password: str) -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User).where(User.username == username, User.is_deleted == False)  # noqa: E712
        )
        user = result.scalars().one_or_none()
        if not user:
            return False

        user.hashed_password = new_password
        user.updated_at = datetime.now(UTC)
        session.add(user)
        await session.commit()
        return True
