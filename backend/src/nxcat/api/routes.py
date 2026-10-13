"""REST endpoints under /api/v1."""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import InstrumentedAttribute, Session

from nxcat.api.schemas import (
    DatasetOut,
    DatasetPage,
    FacetCount,
    Facets,
    Health,
    PreviewOut,
    SearchQuery,
)
from nxcat.api.search import conditions
from nxcat.ingest.reader import ReadError
from nxcat.models.tables import Dataset
from nxcat.preview import DEFAULT_MAX_POINTS, read_preview

router = APIRouter(prefix="/api/v1")


def get_session(request: Request) -> Iterator[Session]:
    engine: Engine = request.app.state.engine
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/health", response_model=Health, tags=["system"])
def health(request: Request, response: Response) -> Health:
    """Is the API up, and can it reach the database?"""
    try:
        with request.app.state.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return Health(status="degraded", database="unreachable")
    return Health(status="ok", database="ok")


@router.get("/datasets", response_model=DatasetPage, tags=["datasets"])
def search_datasets(query: Annotated[SearchQuery, Query()], session: SessionDep) -> DatasetPage:
    """Search datasets. All filters are optional and combined with AND. Newest first."""
    where = conditions(query)
    total = session.scalar(select(func.count()).select_from(Dataset).where(*where)) or 0
    rows = session.scalars(
        select(Dataset)
        .where(*where)
        .order_by(Dataset.start_time.desc(), Dataset.id.desc())
        .offset((query.page - 1) * query.size)
        .limit(query.size)
    ).all()
    return DatasetPage(
        items=[DatasetOut.model_validate(row) for row in rows],
        total=total,
        page=query.page,
        size=query.size,
    )


@router.get("/datasets/{dataset_id}", response_model=DatasetOut, tags=["datasets"])
def get_dataset(dataset_id: int, session: SessionDep) -> DatasetOut:
    row = session.get(Dataset, dataset_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"dataset {dataset_id} not found")
    return DatasetOut.model_validate(row)


@router.get("/datasets/{dataset_id}/preview", response_model=PreviewOut, tags=["datasets"])
def preview_dataset(
    dataset_id: int,
    session: SessionDep,
    max_points: Annotated[int, Query(ge=10, le=2000)] = DEFAULT_MAX_POINTS,
) -> PreviewOut:
    """The main 1-D signal of the file, reduced to at most `max_points` for plotting.

    The file path comes from the catalogue, never from the request, so a caller
    can only read files that ingest has already accepted.
    """
    row = session.get(Dataset, dataset_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"dataset {dataset_id} not found")
    path = Path(row.file_path)
    if not path.is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"the file for dataset {dataset_id} is no longer available",
        )
    try:
        preview = read_preview(path, max_points=max_points)
    except ReadError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f"no preview: {exc}"
        ) from exc
    return PreviewOut(dataset_id=dataset_id, **vars(preview))


@router.get("/facets", response_model=Facets, tags=["datasets"])
def facets(session: SessionDep) -> Facets:
    """How many datasets exist per instrument and per technique (for the filter menus)."""
    return Facets(
        instrument=_counts(session, Dataset.instrument),
        technique=_counts(session, Dataset.technique),
    )


def _counts(session: Session, column: InstrumentedAttribute[str]) -> list[FacetCount]:
    count = func.count().label("count")
    rows = session.execute(
        select(column, count).group_by(column).order_by(count.desc(), column)
    ).all()
    return [FacetCount(value=value, count=n) for value, n in rows]
