from sqlmodel import create_engine

from conf.alembic_runner import upgrade_head
from conf.config import DATABASE_URL

engine = create_engine(DATABASE_URL)


def init_db() -> None:
    upgrade_head()


def close_db() -> None:
    engine.dispose()
