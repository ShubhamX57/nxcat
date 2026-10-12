"""Database connection helpers."""

from sqlalchemy import Engine, create_engine

from nxcat.config import database_url
from nxcat.models.tables import Base


def make_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url(), pool_pre_ping=True)


def create_tables(engine: Engine) -> None:
    """Create any missing tables. Safe to run more than once.

    A migration tool (Alembic) would replace this once the schema needs to change
    on a database that already holds data.
    """
    Base.metadata.create_all(engine)
