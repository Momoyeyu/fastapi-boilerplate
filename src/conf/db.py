from sqlmodel import create_engine

from conf.config import DATABASE_URL
from conf.alembic_runner import upgrade_head

engine = create_engine(DATABASE_URL)


def init_db() -> None:
    upgrade_head()


def close_db() -> None:
    engine.dispose()
