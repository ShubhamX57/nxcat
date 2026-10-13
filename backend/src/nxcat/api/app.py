"""FastAPI application.

Run locally:  uv run uvicorn nxcat.api.app:app --reload
Docs:         http://localhost:8000/api/v1/docs
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from nxcat import __version__
from nxcat.api import admin, auth
from nxcat.api.routes import router
from nxcat.db import create_tables, make_engine

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create missing tables at start-up. If the database is down, start anyway:
    /health then reports it, instead of the API refusing to start."""
    try:
        create_tables(app.state.engine)
    except SQLAlchemyError:
        log.warning("database not reachable at start-up; tables not created")
    yield


def create_app(engine: Engine | None = None) -> FastAPI:
    """Build the app. Tests pass their own engine; normal runs use NXCAT_DATABASE_URL."""
    app = FastAPI(
        title="nxcat",
        version=__version__,
        description="A mini metadata catalogue for neutron data (personal portfolio project).",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.engine = engine or make_engine()
    app.include_router(router)
    app.include_router(auth.router)
    app.include_router(admin.router)
    app.add_exception_handler(OperationalError, _database_unavailable)
    return app


async def _database_unavailable(request: Request, exc: Exception) -> JSONResponse:
    """The database can't be reached: a temporary outage (503), not a bug (500)."""
    log.warning("database unavailable during %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "the database is unavailable; please try again shortly"},
    )


app = create_app()
