from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, Session, select

from conf.db import engine

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True)
    password: str
    nickname: Optional[str] = Field(default=None)
    email: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    role: str = Field(default="user")
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

def create_user(username: str, password: str) -> Optional[User]:
    user = User(username=username, password=password, nickname=username)
    with Session(engine) as session:
        try:
            session.add(user)
            session.commit()
            session.refresh(user)
        except Exception:
            session.rollback()
            return None
    return user

def get_user(username: str) -> Optional[User]:
    with Session(engine) as session:
        return session.exec(select(User).where(User.username == username)).one_or_none()


def update_user_profile(
    username: str,
    *,
    nickname: Optional[str] = None,
    email: Optional[str] = None,
    avatar_url: Optional[str] = None,
) -> Optional[User]:
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

        user.updated_at = datetime.now(timezone.utc)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user
