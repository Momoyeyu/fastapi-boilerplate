from sqlmodel import SQLModel, create_engine

from conf.config import DATABASE_URL

engine = create_engine(DATABASE_URL)


def init_db() -> None:
    from user import model as user_model
    _ = user_model.User

    SQLModel.metadata.create_all(engine)


def close_db() -> None:
    engine.dispose()
