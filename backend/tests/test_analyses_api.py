from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from nxcat.api import analyses
from nxcat.api.app import create_app
from nxcat.ingest.pipeline import ingest_folder
from nxcat.integrations.qens_job import AnalysisError
from nxcat.models.tables import Dataset
from nxcat.security import create_token, hash_password
from nxcat.synthetic import generate

KEY = "k" * 40


@pytest.fixture(scope="module")
def password_hash() -> str:
    return hash_password("a long admin password")


@pytest.fixture
def client(db: Engine, monkeypatch: pytest.MonkeyPatch, password_hash: str) -> Iterator[TestClient]:
    monkeypatch.setenv("NXCAT_SECRET_KEY", KEY)
    monkeypatch.setenv("NXCAT_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("NXCAT_ADMIN_PASSWORD_HASH", password_hash)
    with TestClient(create_app(engine=db)) as c:
        yield c


@pytest.fixture
def ids(db: Engine, tmp_path: Path) -> dict[str, int]:
    """Ingest generated files; return one QENS and one non-QENS dataset id."""
    generate(tmp_path, n=25, seed=3)
    ingest_folder(tmp_path, db)
    with Session(db) as session:
        rows = session.execute(select(Dataset.id, Dataset.technique)).all()
    qens_id = next(i for i, t in rows if t == "QENS")
    other_id = next(i for i, t in rows if t != "QENS")
    return {"qens": qens_id, "other": other_id}


AUTH = {"Authorization": f"Bearer {create_token('admin', KEY, 30)}"}


def start(c: TestClient, dataset_id: int, body: dict[str, Any] | None = None, **kw: Any) -> Any:
    return c.post(f"/api/v1/datasets/{dataset_id}/analyses", json=body or {}, **kw)


def test_start_runs_the_analysis_and_stores_it(client: TestClient, ids: dict[str, int]) -> None:
    response = start(client, ids["qens"], headers=AUTH)
    assert response.status_code == 202
    queued = response.json()
    assert queued["status"] == "queued"
    assert queued["requested_by"] == "admin"
    assert queued["parameters"]["q_min"] == 0.3
    assert queued["software"]["package"] == "qens"
    assert len(queued["software"]["commit"]) == 40
    assert response.headers["Location"] == f"/api/v1/analyses/{queued['id']}"

    done = client.get(f"/api/v1/analyses/{queued['id']}").json()  # background task has run
    assert done["status"] == "done"
    assert done["finished_at"] is not None
    result = done["result"]
    assert result["diffusion_coefficient"] == pytest.approx(result["synthetic_truth"], rel=0.03)


def test_analyses_are_listed_newest_first(client: TestClient, ids: dict[str, int]) -> None:
    first = start(client, ids["qens"], headers=AUTH).json()["id"]
    second = start(client, ids["qens"], {"n_q_bins": 8}, headers=AUTH).json()["id"]
    listed = client.get(f"/api/v1/datasets/{ids['qens']}/analyses").json()
    assert [a["id"] for a in listed] == [second, first]
    assert listed[0]["parameters"]["n_q_bins"] == 8


def test_starting_needs_a_login(client: TestClient, ids: dict[str, int]) -> None:
    assert start(client, ids["qens"]).status_code == 401
    assert client.get(f"/api/v1/datasets/{ids['qens']}/analyses").json() == []


def test_only_qens_datasets_can_be_analysed(client: TestClient, ids: dict[str, int]) -> None:
    response = start(client, ids["other"], headers=AUTH)
    assert response.status_code == 422
    assert "need a QENS dataset" in response.json()["detail"]


def test_unknown_dataset_is_404(client: TestClient) -> None:
    assert start(client, 999999, headers=AUTH).status_code == 404
    assert client.get("/api/v1/datasets/999999/analyses").status_code == 404
    assert client.get("/api/v1/analyses/999999").status_code == 404


def test_missing_file_is_404(client: TestClient, ids: dict[str, int], db: Engine) -> None:
    with Session(db) as session:
        row = session.get(Dataset, ids["qens"])
        assert row is not None
        Path(row.file_path).unlink()
    response = start(client, ids["qens"], headers=AUTH)
    assert response.status_code == 404
    assert "no longer available" in response.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        {"q_min": 2.0, "q_max": 1.0},
        {"n_q_bins": 1},
        {"energy_window": 0},
        {"method": "magic"},
        {"resolution_fwhm_mev": -1},
        {"colour": "blue"},
    ],
)
def test_bad_settings_are_422(
    client: TestClient, ids: dict[str, int], body: dict[str, Any]
) -> None:
    assert start(client, ids["qens"], body, headers=AUTH).status_code == 422


def test_a_failed_analysis_is_stored_with_its_reason(
    client: TestClient, ids: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(path: Path, settings: Any) -> dict[str, Any]:
        raise AnalysisError("only 2 Q-bins could be fitted")

    monkeypatch.setattr(analyses, "run_fickian", fail)
    analysis_id = start(client, ids["qens"], headers=AUTH).json()["id"]
    stored = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert stored["status"] == "failed"
    assert stored["error"] == "only 2 Q-bins could be fitted"
    assert stored["result"] is None


def test_an_unexpected_error_is_stored_without_internal_details(
    client: TestClient, ids: dict[str, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    def crash(path: Path, settings: Any) -> dict[str, Any]:
        raise RuntimeError("secret internal path /srv/x")

    monkeypatch.setattr(analyses, "run_fickian", crash)
    analysis_id = start(client, ids["qens"], headers=AUTH).json()["id"]
    stored = client.get(f"/api/v1/analyses/{analysis_id}").json()
    assert stored["status"] == "failed"
    assert "RuntimeError" in stored["error"]
    assert "/srv/x" not in stored["error"]


def test_background_task_tolerates_a_vanished_record(db: Engine) -> None:
    analyses.run_analysis(123456, db)  # nothing to do, must not raise
