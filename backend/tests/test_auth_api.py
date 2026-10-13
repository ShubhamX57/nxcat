from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response
from sqlalchemy import Engine

from nxcat.api.app import create_app
from nxcat.security import create_token, hash_password
from nxcat.synthetic import Broken, generate

PASSWORD = "a long admin password"
KEY = "s" * 40


@pytest.fixture(scope="module")
def password_hash() -> str:
    return hash_password(PASSWORD)  # scrypt is slow on purpose; hash once


@pytest.fixture
def data_root(tmp_path: Path) -> Path:
    root = tmp_path / "data"
    generate(root / "generated", n=3, seed=31, broken=[Broken.NOT_HDF5])
    (tmp_path / "outside").mkdir()
    return root


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch, password_hash: str, data_root: Path) -> None:
    monkeypatch.setenv("NXCAT_SECRET_KEY", KEY)
    monkeypatch.setenv("NXCAT_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("NXCAT_ADMIN_PASSWORD_HASH", password_hash)
    monkeypatch.setenv("NXCAT_DATA_ROOT", str(data_root))


@pytest.fixture
def client(db: Engine) -> Iterator[TestClient]:
    with TestClient(create_app(engine=db)) as c:
        yield c


def login(client: TestClient, username: str = "admin", password: str = PASSWORD) -> str:
    response = client.post("/api/v1/auth/token", data={"username": username, "password": password})
    assert response.status_code == 200, response.text
    token: str = response.json()["access_token"]
    return token


def ingest(client: TestClient, folder: str, token: str | None) -> Response:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    return client.post("/api/v1/ingest", json={"folder": folder}, headers=headers)


# --- login ---


@pytest.mark.usefixtures("configured")
def test_login_returns_a_bearer_token(client: TestClient) -> None:
    body = client.post(
        "/api/v1/auth/token", data={"username": "admin", "password": PASSWORD}
    ).json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60
    assert body["access_token"].count(".") == 2


@pytest.mark.usefixtures("configured")
@pytest.mark.parametrize(("username", "password"), [("admin", "wrong"), ("root", PASSWORD)])
def test_wrong_login_gives_one_vague_message(
    client: TestClient, username: str, password: str
) -> None:
    response = client.post("/api/v1/auth/token", data={"username": username, "password": password})
    assert response.status_code == 401
    assert response.json() == {"detail": "wrong username or password"}


def test_login_is_off_when_not_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in ("NXCAT_SECRET_KEY", "NXCAT_ADMIN_USERNAME", "NXCAT_ADMIN_PASSWORD_HASH"):
        monkeypatch.delenv(name, raising=False)
    response = client.post("/api/v1/auth/token", data={"username": "a", "password": "b"})
    assert response.status_code == 503


@pytest.mark.usefixtures("configured")
def test_a_short_secret_key_switches_writes_off(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NXCAT_SECRET_KEY", "too-short")
    assert ingest(client, "generated", None).status_code == 503


# --- protected ingest ---


@pytest.mark.usefixtures("configured")
def test_ingest_with_token(client: TestClient) -> None:
    response = ingest(client, "generated", login(client))
    assert response.status_code == 200
    body = response.json()
    assert (body["added"], body["updated"], body["unchanged"]) == (3, 0, 0)
    assert body["folder"] == "generated"
    assert body["started_by"] == "admin"
    assert len(body["failed"]) == 1
    assert body["failed"][0]["file"].startswith("generated/")  # no server paths leaked
    assert client.get("/api/v1/datasets").json()["total"] == 3


@pytest.mark.usefixtures("configured")
@pytest.mark.parametrize(
    "token",
    [
        None,
        "not-a-token",
        create_token("admin", "another-key-another-key-another-key", 30),
        create_token("someone-else", KEY, 30),
        create_token("admin", KEY, -1),  # already expired
    ],
)
def test_ingest_without_a_valid_token_is_401(client: TestClient, token: str | None) -> None:
    response = ingest(client, "generated", token)
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert client.get("/api/v1/datasets").json()["total"] == 0  # nothing happened


@pytest.mark.usefixtures("configured")
@pytest.mark.parametrize("folder", ["../outside", "../../etc", "/etc", "generated/../../outside"])
def test_folders_outside_the_data_root_are_refused(client: TestClient, folder: str) -> None:
    response = ingest(client, folder, login(client))
    assert response.status_code == 400


@pytest.mark.usefixtures("configured")
def test_symbolic_link_out_of_the_data_root_is_refused(client: TestClient, data_root: Path) -> None:
    (data_root / "sneaky").symlink_to(data_root.parent / "outside")
    assert ingest(client, "sneaky", login(client)).status_code == 400


@pytest.mark.usefixtures("configured")
def test_missing_folder_is_404(client: TestClient) -> None:
    assert ingest(client, "nope", login(client)).status_code == 404


@pytest.mark.usefixtures("configured")
def test_empty_folder_name_is_422(client: TestClient) -> None:
    assert ingest(client, "", login(client)).status_code == 422


def test_reading_needs_no_login(client: TestClient) -> None:
    assert client.get("/api/v1/datasets").status_code == 200
