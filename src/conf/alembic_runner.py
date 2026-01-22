from __future__ import annotations

from pathlib import Path

from alembic.command import upgrade
from alembic.config import Config

from conf.config import settings


def _alembic_config() -> Config:
    conf_dir = Path(__file__).resolve().parent
    alembic_cfg = Config(str(conf_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(conf_dir / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
    return alembic_cfg


def upgrade_head() -> None:
    upgrade(_alembic_config(), "head")
