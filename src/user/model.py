from datetime import UTC, datetime

from sqlmodel import Field, Session, SQLModel, select

from conf.db import engine


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True)
    password: str
    nickname: str | None = Field(default=None)
    email: str | None = Field(default=None)
    avatar_url: str | None = Field(default=None)
    role: str = Field(default="user")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def create_user(username: str, password: str, *, role: str = "user") -> User | None:
    user = User(username=username, password=password, nickname=username, role=role)
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
        return session.exec(select(User).where(User.username == username)).one_or_none()


def update_user_profile(
    username: str,
    *,
    nickname: str | None = None,
    email: str | None = None,
    avatar_url: str | None = None,
) -> User | None:
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).one_or_none()
        if not user:
            return None

        if nickname is not None:
            user.nickname = nickname
        if email is not None:
            user.email = email
        if avatar_url is not None:
            user.avatar_url = avatar_url

        user.updated_at = datetime.now(UTC)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
