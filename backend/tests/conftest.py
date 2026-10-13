"""Shared test fixtures.

Database tests use NXCAT_TEST_DATABASE_URL (default: the local `nxcat_test`
database from docker compose). If no database is reachable they are skipped,
unless NXCAT_REQUIRE_DB=1 is set (as in CI), where a missing database is a failure.
"""

import os
import random
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError

from nxcat.db import create_tables, make_engine
from nxcat.models.metadata import DatasetMetadata
from nxcat.synthetic import random_metadata, write_nexus

TEST_DATABASE_URL = os.environ.get(
    "NXCAT_TEST_DATABASE_URL", "postgresql+psycopg://nxcat:nxcat@localhost:5432/nxcat_test"
)


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    eng = make_engine(TEST_DATABASE_URL)
    try:
        with eng.connect():
            pass
    except OperationalError as exc:
        eng.dispose()
        if os.environ.get("NXCAT_REQUIRE_DB") == "1":
            pytest.fail(f"test database not reachable: {exc}")
        pytest.skip("test database not reachable (start it with: docker compose up -d db)")
    create_tables(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine: Engine) -> Engine:
    """An empty database for each test."""
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE dataset, ingest_error, analysis RESTART IDENTITY"))
    return engine


@pytest.fixture
def nexus_file(tmp_path: Path) -> tuple[Path, DatasetMetadata]:
    """One valid generated file and the metadata it was built from."""
    rng = random.Random(3)
    meta = random_metadata(rng, run_number=4242)
    return write_nexus(tmp_path / "one.nxs", meta, rng), meta
