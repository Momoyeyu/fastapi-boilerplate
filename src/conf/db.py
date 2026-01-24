from sqlmodel import create_engine

from conf.config import settings

engine = create_engine(settings.database_url)


def close_db() -> None:
    engine.dispose()
