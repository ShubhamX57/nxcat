import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from nxcat.ai.proposer import Complete
from nxcat.api.app import create_app
from tests.test_api import add


def model_replying(obj: Any) -> Complete:
    def complete(messages: list[dict[str, str]]) -> str:
        return json.dumps(obj)

    return complete


def client_with(db: Engine, complete: Complete | None) -> Iterator[TestClient]:
    with TestClient(create_app(engine=db, complete=complete)) as c:
        yield c


@pytest.fixture
def catalogue(db: Engine) -> None:
    add(db, n=1, instrument="LET")
    add(db, n=2, instrument="MARI", technique="INS")


def ask(c: TestClient, question: str) -> Any:
    return c.post("/api/v1/search/ask", json={"question": question})


@pytest.mark.usefixtures("catalogue")
def test_a_valid_proposal_returns_the_filter_and_no_datasets(db: Engine) -> None:
    complete = model_replying({"filter": {"instrument": "LET", "temp_min": 250}})
    for c in client_with(db, complete):
        response = ask(c, "LET above 250 K")
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "status": "proposed",
        "filter": {"instrument": "LET", "temp_min": 250.0},
        "description": ["Instrument is LET", "Temperature at least 250 K"],
    }
    assert "items" not in body  # the endpoint never returns results


@pytest.mark.usefixtures("catalogue")
def test_the_proposed_filter_runs_unchanged_on_the_search_endpoint(db: Engine) -> None:
    complete = model_replying({"filter": {"instrument": "MARI"}})
    for c in client_with(db, complete):
        proposed = ask(c, "MARI runs").json()["filter"]
        results = c.get("/api/v1/datasets", params=proposed).json()
    assert results["total"] == 1
    assert results["items"][0]["instrument"] == "MARI"


@pytest.mark.usefixtures("catalogue")
def test_instruments_come_from_the_catalogue(db: Engine) -> None:
    seen: list[str] = []

    def spy(messages: list[dict[str, str]]) -> str:
        seen.append(messages[0]["content"])
        return json.dumps({"filter": {"instrument": "BIFROST"}})  # real, but not catalogued

    for c in client_with(db, spy):
        body = ask(c, "BIFROST runs").json()
    assert "LET, MARI" in seen[0]
    assert body == {
        "status": "rejected",
        "description": [],
        "kind": "invalid",
        "reason": "I could not turn that into a valid search. Please rephrase it.",
    }


@pytest.mark.usefixtures("catalogue")
@pytest.mark.parametrize(
    ("model_output", "kind"),
    [
        ({"out_of_scope": "a science question"}, "out_of_scope"),
        ({"unclear": "which temperature is cold?"}, "unclear"),
        ({"filter": {"technique": "QENS", "drop": "table"}}, "invalid"),
    ],
)
def test_rejections(db: Engine, model_output: Any, kind: str) -> None:
    for c in client_with(db, model_replying(model_output)):
        body = ask(c, "something").json()
    assert body["status"] == "rejected"
    assert body["kind"] == kind
    assert "filter" not in body


def test_not_configured_is_503(db: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NXCAT_LLM_MODEL", raising=False)
    for c in client_with(db, None):
        response = ask(c, "LET runs")
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]


def test_model_failure_is_503_without_details(db: Engine) -> None:
    def broken(messages: list[dict[str, str]]) -> str:
        raise ConnectionError("model server at 10.0.0.5 refused the connection")

    for c in client_with(db, broken):
        response = ask(c, "LET runs")
    assert response.status_code == 503
    assert "10.0.0.5" not in response.text  # internal details are not leaked


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "x" * 301}])
def test_bad_requests_are_422(db: Engine, body: dict[str, str]) -> None:
    for c in client_with(db, model_replying({"filter": {"q": "x"}})):
        assert c.post("/api/v1/search/ask", json=body).status_code == 422


def test_model_configured_from_environment(db: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NXCAT_LLM_MODEL", "ollama/test-model")
    app = create_app(engine=db)
    assert app.state.complete is not None
