from __future__ import annotations

from pathlib import Path

from alembic.command import upgrade
from alembic.config import Config

from conf.config import DATABASE_URL


def _alembic_config() -> Config:
    conf_dir = Path(__file__).resolve().parent
    config = Config(str(conf_dir / "alembic.ini"))
    config.set_main_option("script_location", str(conf_dir / "alembic"))
    config.set_main_option("sqlalchemy.url", DATABASE_URL)
    return config


def upgrade_head() -> None:
    upgrade(_alembic_config(), "head")
