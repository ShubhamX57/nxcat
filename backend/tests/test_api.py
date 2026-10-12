from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from nxcat.api.app import create_app
from nxcat.db import make_engine
from nxcat.models.tables import Dataset

T0 = datetime(2025, 1, 1, tzinfo=UTC)


def add(engine: Engine, **overrides: Any) -> int:
    """Insert one dataset row with sensible defaults; return its id."""
    n = overrides.pop("n", 0)
    values: dict[str, Any] = {
        "file_path": f"/data/file_{n}_{overrides.get('title', '')}.nxs",
        "checksum": "0" * 64,
        "file_size_bytes": 1000,
        "schema_version": "1",
        "title": "Water QENS 300 K",
        "instrument": "LET",
        "technique": "QENS",
        "run_number": 1000 + n,
        "sample_name": "water",
        "sample_temperature_k": 300.0,
        "start_time": T0 + timedelta(days=n),
        "end_time": None,
        "facility": "ISIS",
        "proposal_id": None,
    } | overrides
    with Session(engine) as session:
        row = Dataset(**values)
        session.add(row)
        session.commit()
        return row.id


@pytest.fixture
def client(db: Engine) -> Iterator[TestClient]:
    with TestClient(create_app(engine=db)) as c:
        yield c


@pytest.fixture
def catalogue(db: Engine) -> dict[str, int]:
    """Five known datasets."""
    return {
        "let_water": add(db, n=1),
        "let_benzene": add(
            db, n=2, title="Benzene QENS 260 K", sample_name="benzene", sample_temperature_k=260.0
        ),
        "mari_benzene": add(
            db,
            n=3,
            title="Benzene INS 5 K",
            instrument="MARI",
            technique="INS",
            sample_name="benzene",
            sample_temperature_k=5.0,
        ),
        "loki_no_temp": add(
            db,
            n=4,
            title="Polymer SANS",
            instrument="LOKI",
            technique="SANS",
            sample_name="PEO",
            sample_temperature_k=None,
            facility="ESS",
        ),
        "let_old": add(db, n=-400, title="Old water run"),
    }


def ids(response: Any) -> list[int]:
    assert response.status_code == 200, response.text
    return [item["id"] for item in response.json()["items"]]


# --- health and docs ---


def test_health_ok(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_reports_unreachable_database() -> None:
    bad = make_engine("postgresql+psycopg://nobody:wrong@localhost:1/none")
    with TestClient(create_app(engine=bad)) as c:
        response = c.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json()["database"] == "unreachable"


@pytest.mark.parametrize("path", ["/api/v1/datasets", "/api/v1/datasets/1", "/api/v1/facets"])
def test_database_outage_is_503_with_a_reason(path: str) -> None:
    bad = make_engine("postgresql+psycopg://nobody:wrong@localhost:1/none")
    with TestClient(create_app(engine=bad)) as c:
        response = c.get(path)
    assert response.status_code == 503
    assert "database is unavailable" in response.json()["detail"]


def test_openapi_docs_are_served(client: TestClient) -> None:
    schema = client.get("/api/v1/openapi.json").json()
    assert "/api/v1/datasets" in schema["paths"]
    assert client.get("/api/v1/docs").status_code == 200


# --- search ---


def test_search_without_filters_returns_all_newest_first(
    client: TestClient, catalogue: dict[str, int]
) -> None:
    c = catalogue
    assert ids(client.get("/api/v1/datasets")) == [
        c["loki_no_temp"],
        c["mari_benzene"],
        c["let_benzene"],
        c["let_water"],
        c["let_old"],
    ]


def test_empty_catalogue(client: TestClient) -> None:
    body = client.get("/api/v1/datasets").json()
    assert body == {"items": [], "total": 0, "page": 1, "size": 20}


def test_paging(client: TestClient, catalogue: dict[str, int]) -> None:
    body = client.get("/api/v1/datasets", params={"size": 2, "page": 2}).json()
    assert body["total"] == 5
    assert [i["id"] for i in body["items"]] == [catalogue["let_benzene"], catalogue["let_water"]]
    assert client.get("/api/v1/datasets", params={"size": 2, "page": 9}).json()["items"] == []


@pytest.mark.parametrize("params", [{"page": 0}, {"size": 0}, {"size": 101}, {"page": "x"}])
def test_bad_paging_is_rejected(client: TestClient, params: dict[str, Any]) -> None:
    assert client.get("/api/v1/datasets", params=params).status_code == 422


def test_filter_by_instrument_ignores_case(client: TestClient, catalogue: dict[str, int]) -> None:
    assert ids(client.get("/api/v1/datasets", params={"instrument": "mari"})) == [
        catalogue["mari_benzene"]
    ]


def test_filter_by_technique(client: TestClient, catalogue: dict[str, int]) -> None:
    assert ids(client.get("/api/v1/datasets", params={"technique": "SANS"})) == [
        catalogue["loki_no_temp"]
    ]


def test_unknown_technique_is_rejected(client: TestClient) -> None:
    assert client.get("/api/v1/datasets", params={"technique": "MAGIC"}).status_code == 422


def test_filter_by_temperature_range(client: TestClient, catalogue: dict[str, int]) -> None:
    found = ids(client.get("/api/v1/datasets", params={"temp_min": 100, "temp_max": 280}))
    assert found == [catalogue["let_benzene"]]


def test_temperature_filter_excludes_unknown_temperature(
    client: TestClient, catalogue: dict[str, int]
) -> None:
    assert catalogue["loki_no_temp"] not in ids(
        client.get("/api/v1/datasets", params={"temp_min": 0})
    )


@pytest.mark.parametrize(
    "params",
    [
        {"temp_min": 300, "temp_max": 100},
        {"temp_min": -1},
        {"start_after": "2025-06-01T00:00:00Z", "start_before": "2025-01-01T00:00:00Z"},
        {"start_after": "2025-06-01T00:00:00"},  # no timezone
        {"colour": "blue"},  # unknown parameter
        {"q": ""},
        {"q": "x" * 201},
    ],
)
def test_invalid_filters_are_rejected(client: TestClient, params: dict[str, Any]) -> None:
    assert client.get("/api/v1/datasets", params=params).status_code == 422


def test_filter_by_start_date(client: TestClient, catalogue: dict[str, int]) -> None:
    found = ids(
        client.get(
            "/api/v1/datasets",
            params={"start_after": "2025-01-02T12:00:00Z", "start_before": "2025-01-04T12:00:00Z"},
        )
    )
    assert found == [catalogue["mari_benzene"], catalogue["let_benzene"]]


def test_free_text_search(client: TestClient, catalogue: dict[str, int]) -> None:
    found = ids(client.get("/api/v1/datasets", params={"q": "benzene"}))
    assert set(found) == {catalogue["let_benzene"], catalogue["mari_benzene"]}


def test_free_text_uses_word_stems(client: TestClient, catalogue: dict[str, int]) -> None:
    assert catalogue["loki_no_temp"] in ids(
        client.get("/api/v1/datasets", params={"q": "polymers"})
    )


def test_free_text_tolerates_odd_input(client: TestClient, catalogue: dict[str, int]) -> None:
    for q in ['"water', "water -old", "a & b | !", "'; DROP TABLE dataset; --"]:
        assert client.get("/api/v1/datasets", params={"q": q}).status_code == 200
    assert client.get("/api/v1/datasets").json()["total"] == 5  # table still there


def test_filters_combine_with_and(client: TestClient, catalogue: dict[str, int]) -> None:
    found = ids(
        client.get(
            "/api/v1/datasets", params={"q": "benzene", "instrument": "LET", "temp_min": 200}
        )
    )
    assert found == [catalogue["let_benzene"]]


def test_times_are_returned_in_utc(client: TestClient, catalogue: dict[str, int]) -> None:
    item = client.get(f"/api/v1/datasets/{catalogue['let_water']}").json()
    assert item["start_time"] == "2025-01-02T00:00:00Z"


# --- detail ---


def test_dataset_detail(client: TestClient, catalogue: dict[str, int]) -> None:
    body = client.get(f"/api/v1/datasets/{catalogue['mari_benzene']}").json()
    assert body["instrument"] == "MARI"
    assert body["technique"] == "INS"
    assert body["sample_temperature_k"] == 5.0
    assert "search_vector" not in body


def test_unknown_dataset_is_404(client: TestClient) -> None:
    response = client.get("/api/v1/datasets/999999")
    assert response.status_code == 404
    assert response.json() == {"detail": "dataset 999999 not found"}


def test_non_integer_id_is_422(client: TestClient) -> None:
    assert client.get("/api/v1/datasets/abc").status_code == 422


# --- facets ---


def test_facets(client: TestClient, catalogue: dict[str, int]) -> None:
    body = client.get("/api/v1/facets").json()
    assert body["instrument"] == [
        {"value": "LET", "count": 3},
        {"value": "LOKI", "count": 1},
        {"value": "MARI", "count": 1},
    ]
    assert body["technique"][0] == {"value": "QENS", "count": 3}


def test_facets_on_empty_catalogue(client: TestClient) -> None:
    assert client.get("/api/v1/facets").json() == {"instrument": [], "technique": []}
