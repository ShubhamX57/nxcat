"""FastAPI application.

Run locally:  uv run uvicorn nxcat.api.app:app --reload
Docs:         http://localhost:8000/api/v1/docs
"""

from fastapi import FastAPI
from sqlalchemy import Engine

from nxcat import __version__
from nxcat.api.routes import router
from nxcat.db import make_engine


def create_app(engine: Engine | None = None) -> FastAPI:
    """Build the app. Tests pass their own engine; normal runs use NXCAT_DATABASE_URL."""
    app = FastAPI(
        title="nxcat",
        version=__version__,
        description="A mini metadata catalogue for neutron data (personal portfolio project).",
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
    )
    app.state.engine = engine or make_engine()
    app.include_router(router)
    return app


app = create_app()
