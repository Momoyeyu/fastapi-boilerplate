from sqlmodel import create_engine

from conf.alembic_runner import upgrade_head
from conf.config import settings

engine = create_engine(settings.database_url)


def init_db() -> None:
    upgrade_head()


def close_db() -> None:
    engine.dispose()
