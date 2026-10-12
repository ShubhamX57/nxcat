from pathlib import Path

import h5py
import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from nxcat.ingest.pipeline import find_files, ingest_folder, main
from nxcat.models.metadata import SCHEMA_VERSION
from nxcat.models.tables import Dataset, IngestError
from nxcat.synthetic import Broken, generate


def count(engine: Engine, model: type[Dataset] | type[IngestError]) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(model)) or 0


def test_valid_files_are_added(db: Engine, tmp_path: Path) -> None:
    generate(tmp_path, n=10, seed=1)
    report = ingest_folder(tmp_path, db)
    assert (report.added, report.updated, report.unchanged, report.failed) == (10, 0, 0, [])
    assert count(db, Dataset) == 10


def test_stored_row_matches_the_file(db: Engine, tmp_path: Path) -> None:
    [path] = generate(tmp_path, n=1, seed=2)
    ingest_folder(tmp_path, db)
    with Session(db) as session:
        row = session.scalars(select(Dataset)).one()
    assert row.file_path == str(path.resolve())
    assert row.file_size_bytes == path.stat().st_size
    assert len(row.checksum) == 64
    assert row.schema_version == SCHEMA_VERSION
    assert row.start_time.tzinfo is not None


def test_second_run_changes_nothing(db: Engine, tmp_path: Path) -> None:
    generate(tmp_path, n=5, seed=3)
    ingest_folder(tmp_path, db)
    report = ingest_folder(tmp_path, db)
    assert (report.added, report.updated, report.unchanged) == (0, 0, 5)
    assert count(db, Dataset) == 5


def test_changed_file_is_updated_not_duplicated(db: Engine, tmp_path: Path) -> None:
    [path] = generate(tmp_path, n=1, seed=4)
    ingest_folder(tmp_path, db)
    with h5py.File(path, "a") as f:
        del f["entry/title"]
        f["entry/title"] = "Corrected title"
    report = ingest_folder(tmp_path, db)
    assert (report.added, report.updated) == (0, 1)
    with Session(db) as session:
        assert session.scalars(select(Dataset.title)).all() == ["Corrected title"]


def test_bad_files_are_logged_and_skipped(db: Engine, tmp_path: Path) -> None:
    generate(tmp_path, n=3, seed=5, broken=list(Broken))
    report = ingest_folder(tmp_path, db)
    assert report.added == 3
    assert len(report.failed) == len(Broken)
    assert count(db, Dataset) == 3
    with Session(db) as session:
        errors = session.scalars(select(IngestError)).all()
    assert len(errors) == len(Broken)
    assert all(error.reason for error in errors)


def test_unreadable_file_is_logged(
    db: Engine, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    generate(tmp_path, n=1, seed=6)

    def no_permission(path: Path, chunk_size: int = 0) -> str:
        raise PermissionError("permission denied")

    monkeypatch.setattr("nxcat.ingest.pipeline.sha256_of", no_permission)
    report = ingest_folder(tmp_path, db)
    assert report.failed[0][1] == "cannot read file: permission denied"


def test_only_nexus_files_are_considered(tmp_path: Path) -> None:
    generate(tmp_path / "sub", n=2, seed=7)
    (tmp_path / "notes.txt").write_text("not data")
    (tmp_path / "UPPER.NXS").write_bytes(b"")
    found = find_files(tmp_path)
    assert "UPPER.NXS" in {p.name for p in found}  # suffix check ignores case
    assert found == sorted(found)  # stable order
    assert len(found) == 3
    assert all(p.suffix.lower() == ".nxs" for p in found)


def test_missing_folder_is_an_error(db: Engine, tmp_path: Path) -> None:
    with pytest.raises(NotADirectoryError):
        ingest_folder(tmp_path / "missing", db)


def test_full_text_search_finds_sample(db: Engine, tmp_path: Path) -> None:
    generate(tmp_path, n=30, seed=8)
    ingest_folder(tmp_path, db)
    with db.connect() as conn:
        samples = conn.scalars(
            text(
                "SELECT sample_name FROM dataset "
                "WHERE search_vector @@ plainto_tsquery('english', :q)"
            ),
            {"q": "benzene"},
        ).all()
    assert samples
    assert set(samples) == {"benzene"}


def test_cli_ingests_and_prints_summary(
    db: Engine, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    generate(tmp_path, n=2, seed=9, broken=[Broken.NOT_HDF5])
    url = db.url.render_as_string(hide_password=False)
    main([str(tmp_path), "--database-url", url])
    out = capsys.readouterr().out
    assert "FAILED" in out
    assert "added 2, updated 0, unchanged 0, failed 1" in out


def test_cli_rejects_missing_folder(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main([str(tmp_path / "missing")])
