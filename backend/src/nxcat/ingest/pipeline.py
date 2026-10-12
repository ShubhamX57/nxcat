"""Ingest a folder of NeXus files into the database.

Rules:
- A bad *file* is recorded in `ingest_error` and skipped; the run carries on.
- A *database* problem is not the file's fault, so it stops the run with an error.
- Running ingest twice on the same folder changes nothing (files are matched by
  path, and unchanged files are recognised by their checksum).
"""

import argparse
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import Engine, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nxcat.db import create_tables, make_engine
from nxcat.ingest.reader import ReadError, read_metadata, sha256_of
from nxcat.models.metadata import SCHEMA_VERSION
from nxcat.models.tables import Dataset, IngestError

NEXUS_SUFFIXES = frozenset({".nxs", ".nxspe", ".h5", ".hdf5", ".nx5"})


@dataclass
class IngestReport:
    added: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"added {self.added}, updated {self.updated}, "
            f"unchanged {self.unchanged}, failed {len(self.failed)}"
        )


def find_files(folder: Path) -> list[Path]:
    """All NeXus-like files under `folder`, in a stable order."""
    return sorted(
        p for p in folder.rglob("*") if p.is_file() and p.suffix.lower() in NEXUS_SUFFIXES
    )


def ingest_folder(folder: Path, engine: Engine) -> IngestReport:
    if not folder.is_dir():
        raise NotADirectoryError(folder)
    report = IngestReport()
    with Session(engine) as session:
        for path in find_files(folder):
            _ingest_file(path.resolve(), session, report)
    return report


def _ingest_file(path: Path, session: Session, report: IngestReport) -> None:
    file_path = str(path)
    try:
        checksum = sha256_of(path)
        previous = session.scalar(select(Dataset.checksum).where(Dataset.file_path == file_path))
        if previous == checksum:
            report.unchanged += 1
            return
        meta = read_metadata(path)
    except (ReadError, OSError) as exc:
        reason = str(exc) if isinstance(exc, ReadError) else f"cannot read file: {exc}"
        session.add(IngestError(file_path=file_path, reason=reason))
        session.commit()
        report.failed.append((path, reason))
        return

    values = meta.model_dump() | {
        "technique": meta.technique.value,
        "file_path": file_path,
        "checksum": checksum,
        "file_size_bytes": path.stat().st_size,
        "schema_version": SCHEMA_VERSION,
    }
    statement = insert(Dataset).values(**values)
    statement = statement.on_conflict_do_update(
        index_elements=[Dataset.file_path],
        set_={key: statement.excluded[key] for key in values if key != "file_path"},
    )
    session.execute(statement)
    session.commit()
    if previous is None:
        report.added += 1
    else:
        report.updated += 1


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Ingest a folder of NeXus files.")
    parser.add_argument("folder", type=Path)
    parser.add_argument("--database-url", help="default: NXCAT_DATABASE_URL or local database")
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        parser.error(f"not a folder: {args.folder}")

    engine = make_engine(args.database_url)
    create_tables(engine)
    report = ingest_folder(args.folder, engine)
    for path, reason in report.failed:
        print(f"FAILED {path}: {reason}")
    print(f"Ingest finished: {report.summary()}")
