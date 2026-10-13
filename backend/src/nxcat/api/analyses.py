"""Analyses: run qens on a QENS dataset and read back the stored results.

Starting an analysis is a write action, so it needs a login token. It returns at
once (202 Accepted) with a queued record; the work runs in the background and the
record moves to "done" or "failed". Reading analyses is open to everyone.
"""

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Self

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from nxcat import __version__
from nxcat.api.auth import AdminDep
from nxcat.api.routes import SessionDep
from nxcat.integrations.qens_job import (
    METHOD,
    AnalysisError,
    Settings,
    qens_provenance,
    run_fickian,
)
from nxcat.models.tables import Analysis, Dataset

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["analyses"])


class AnalysisRequest(BaseModel):
    """Settings for a qens Fickian-diffusion analysis. All have sensible defaults."""

    model_config = ConfigDict(extra="forbid")

    method: Literal["qens-fickian"] = METHOD
    q_min: float = Field(default=0.3, ge=0, le=10, description="Å⁻¹")
    q_max: float = Field(default=2.5, gt=0, le=10, description="Å⁻¹")
    energy_window: float = Field(default=1.25, gt=0, le=10, description="± meV")
    n_q_bins: int = Field(default=12, ge=3, le=50)
    resolution_fwhm_mev: float | None = Field(
        default=None, gt=0, le=10, description="override the instrument resolution"
    )

    @model_validator(mode="after")
    def _q_range(self) -> Self:
        if self.q_min >= self.q_max:
            raise ValueError("q_min must be smaller than q_max")
        return self


class AnalysisOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    dataset_id: int
    method: str
    status: Literal["queued", "running", "done", "failed"]
    parameters: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    software: dict[str, Any]
    requested_by: str
    created_at: datetime
    finished_at: datetime | None


def run_analysis(analysis_id: int, engine: Engine) -> None:
    """Background task: run the job and store the outcome. Never raises."""
    with Session(engine) as session:
        analysis = session.get(Analysis, analysis_id)
        if analysis is None:
            return
        dataset = session.get(Dataset, analysis.dataset_id)
        analysis.status = "running"
        session.commit()
        try:
            if dataset is None:
                raise AnalysisError("the dataset no longer exists")
            params = {k: v for k, v in analysis.parameters.items() if k != "method"}
            analysis.result = run_fickian(Path(dataset.file_path), Settings(**params))
            analysis.status = "done"
        except AnalysisError as exc:
            analysis.status, analysis.error = "failed", str(exc)
        except Exception as exc:  # anything unexpected from the scientific code
            log.exception("analysis %s failed", analysis_id)
            analysis.status = "failed"
            analysis.error = f"the analysis stopped with an unexpected error ({type(exc).__name__})"
        analysis.finished_at = datetime.now(UTC)
        session.commit()


@router.post(
    "/datasets/{dataset_id}/analyses",
    response_model=AnalysisOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_analysis(
    dataset_id: int,
    body: AnalysisRequest,
    request: Request,
    response: Response,
    background: BackgroundTasks,
    session: SessionDep,
    user: AdminDep,
) -> AnalysisOut:
    """Queue a qens analysis of a QENS dataset (login required)."""
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"dataset {dataset_id} not found")
    if dataset.technique != "QENS":
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"qens analyses need a QENS dataset; this one is {dataset.technique}",
        )
    if not Path(dataset.file_path).is_file():
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"the file for dataset {dataset_id} is no longer available",
        )
    analysis = Analysis(
        dataset_id=dataset_id,
        method=body.method,
        status="queued",
        parameters=body.model_dump(),
        software={"nxcat": __version__, **qens_provenance()},
        requested_by=user,
    )
    session.add(analysis)
    session.commit()
    background.add_task(run_analysis, analysis.id, request.app.state.engine)
    response.headers["Location"] = f"/api/v1/analyses/{analysis.id}"
    return AnalysisOut.model_validate(analysis)


@router.get("/datasets/{dataset_id}/analyses", response_model=list[AnalysisOut])
def list_analyses(dataset_id: int, session: SessionDep) -> list[AnalysisOut]:
    """All analyses of a dataset, newest first."""
    if session.get(Dataset, dataset_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"dataset {dataset_id} not found")
    rows = session.scalars(
        select(Analysis)
        .where(Analysis.dataset_id == dataset_id)
        .order_by(Analysis.created_at.desc(), Analysis.id.desc())
    ).all()
    return [AnalysisOut.model_validate(row) for row in rows]


@router.get("/analyses/{analysis_id}", response_model=AnalysisOut)
def get_analysis(analysis_id: int, session: SessionDep) -> AnalysisOut:
    row = session.get(Analysis, analysis_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"analysis {analysis_id} not found")
    return AnalysisOut.model_validate(row)
