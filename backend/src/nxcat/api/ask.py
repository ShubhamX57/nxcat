"""POST /api/v1/search/ask: a plain-English question in, a *proposed* filter out.

This endpoint never runs a search and never returns datasets. The web app shows the
proposal in plain words, and only searches when the user presses Run, through the
normal GET /api/v1/datasets endpoint with its normal validation.
"""

import logging
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from nxcat.ai.proposer import MAX_QUESTION_LENGTH, Complete, Proposal, propose
from nxcat.api.schemas import SearchFilters
from nxcat.models.tables import Dataset

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/search", tags=["search"])


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)


class AskResponse(BaseModel):
    status: Literal["proposed", "rejected"]
    filter: SearchFilters | None = None
    description: list[str] = []
    kind: Literal["out_of_scope", "unclear", "invalid"] | None = None
    reason: str | None = None


@router.post("/ask", response_model=AskResponse, response_model_exclude_none=True)
def ask(body: AskRequest, request: Request) -> AskResponse:
    complete: Complete | None = request.app.state.complete
    if complete is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="plain-English search is not configured on this server",
        )
    with Session(request.app.state.engine) as session:
        instruments = set(session.scalars(select(Dataset.instrument).distinct()))
    try:
        outcome = propose(body.question, complete, instruments, datetime.now(UTC).date())
    except Exception:  # any failure of the model service, which we do not control
        log.exception("language model call failed")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the language model is not reachable; please try again or use the filters",
        ) from None
    if isinstance(outcome, Proposal):
        return AskResponse(
            status="proposed", filter=outcome.filters, description=outcome.description
        )
    return AskResponse(status="rejected", kind=outcome.kind, reason=outcome.reason)
