from datetime import UTC, datetime

from sqlmodel import Field, Session, SQLModel, select

from conf.db import engine


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    password: str
    nickname: str | None = Field(default=None)
    avatar_url: str | None = Field(default=None)
    role: str = Field(default="user")
    is_active: bool = Field(default=True)
    invitation_code_id: int | None = Field(default=None)
    is_deleted: bool = Field(default=False)
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def create_user(
    username: str,
    password: str,
    email: str,
    *,
    role: str = "user",
    invitation_code_id: int | None = None,
) -> User | None:
    user = User(
        username=username,
        password=password,
        email=email,
        nickname=username,
        role=role,
        invitation_code_id=invitation_code_id,
    )
    with Session(engine) as session:
        try:
            session.add(user)
            session.commit()
            session.refresh(user)
        except Exception:
            session.rollback()
            return None
    return user


def get_user(username: str) -> User | None:
    with Session(engine) as session:
        return session.exec(
            select(User).where(User.username == username, User.is_deleted == False)  # noqa: E712
        ).one_or_none()


def get_user_by_email(email: str) -> User | None:
    with Session(engine) as session:
        return session.exec(
            select(User).where(User.email == email.lower(), User.is_deleted == False)  # noqa: E712
        ).one_or_none()


def get_user_by_identifier(identifier: str) -> User | None:
    if "@" in identifier:
        return get_user_by_email(identifier)
    return get_user(identifier)


def email_exists(email: str) -> bool:
    with Session(engine) as session:
        return (
            session.exec(
                select(User).where(User.email == email.lower(), User.is_deleted == False)  # noqa: E712
            ).one_or_none()
            is not None
        )


def username_exists(username: str) -> bool:
    with Session(engine) as session:
        return (
            session.exec(
                select(User).where(User.username == username, User.is_deleted == False)  # noqa: E712
            ).one_or_none()
            is not None
        )


def update_user_profile(
    username: str,
    *,
    nickname: str | None = None,
    email: str | None = None,
    avatar_url: str | None = None,
) -> User | None:
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.username == username, User.is_deleted == False)  # noqa: E712
        ).one_or_none()
        if not user:
            return None

        if nickname is not None:
            user.nickname = nickname
        if email is not None:
            user.email = email.lower()
        if avatar_url is not None:
            user.avatar_url = avatar_url

        user.updated_at = datetime.now(UTC)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


def update_user_password(username: str, new_password: str) -> bool:
    with Session(engine) as session:
        user = session.exec(
            select(User).where(User.username == username, User.is_deleted == False)  # noqa: E712
        ).one_or_none()
        if not user:
            return False

        user.password = new_password
        user.updated_at = datetime.now(UTC)
        session.add(user)
        session.commit()
        return True
