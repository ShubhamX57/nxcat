"""Write endpoints. Every route here needs a login token."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from nxcat import config
from nxcat.api.auth import AdminDep
from nxcat.ingest.pipeline import ingest_folder

router = APIRouter(prefix="/api/v1", tags=["admin"])


class IngestRequest(BaseModel):
    folder: str = Field(
        min_length=1,
        max_length=500,
        description="folder inside the server's data root, e.g. 'generated'",
        examples=["generated"],
    )


class IngestFailure(BaseModel):
    file: str
    reason: str


class IngestResult(BaseModel):
    folder: str
    added: int
    updated: int
    unchanged: int
    failed: list[IngestFailure]
    started_by: str


def resolve_inside(root: Path, folder: str) -> Path:
    """Turn a user-supplied folder into a real path that is guaranteed to be inside `root`.

    Resolving first (which follows '..' and symbolic links) and then checking is what
    stops requests like '../../etc' or a link that points outside the data root.
    """
    root = root.resolve()
    target = (root / folder).resolve()
    if not target.is_relative_to(root):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="the folder must be inside the data root"
        )
    if not target.is_dir():
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"no such folder: {folder}")
    return target


@router.post("/ingest", response_model=IngestResult)
def start_ingest(body: IngestRequest, request: Request, user: AdminDep) -> IngestResult:
    """Catalogue every NeXus file in a folder of the data root (runs to completion).

    Runs inside the request, which is fine for hundreds of files. Thousands would
    need a background job queue instead.
    """
    root = config.data_root()
    folder = resolve_inside(root, body.folder)
    report = ingest_folder(folder, request.app.state.engine)
    return IngestResult(
        folder=str(folder.relative_to(root.resolve())) or ".",
        added=report.added,
        updated=report.updated,
        unchanged=report.unchanged,
        failed=[
            IngestFailure(file=str(path.relative_to(root.resolve())), reason=reason)
            for path, reason in report.failed
        ],
        started_by=user,
    )
