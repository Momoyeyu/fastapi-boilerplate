from typing import Optional

from sqlmodel import Field, SQLModel, Session, select

from conf.db import engine

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True)
    password: str

def create_user(username: str, password: str) -> Optional[User]:
    user = User(username=username, password=password)
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
