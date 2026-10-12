"""Settings read from environment variables."""

import os

DEFAULT_DATABASE_URL = "postgresql+psycopg://nxcat:nxcat@localhost:5432/nxcat"


def database_url() -> str:
    """Database to use. Set NXCAT_DATABASE_URL to override the local default."""
    return os.environ.get("NXCAT_DATABASE_URL", DEFAULT_DATABASE_URL)
