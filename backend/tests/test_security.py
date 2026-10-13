from datetime import UTC, datetime, timedelta

import jwt
import pytest

from nxcat.security import (
    InvalidTokenError,
    check_login,
    create_token,
    hash_password,
    main,
    read_token,
    verify_password,
)

KEY = "k" * 32


def test_password_round_trip() -> None:
    stored = hash_password("correct horse battery")
    assert stored.startswith("scrypt$")
    assert "correct horse" not in stored
    assert verify_password("correct horse battery", stored)
    assert not verify_password("wrong password!!", stored)


def test_same_password_gets_different_salt() -> None:
    assert hash_password("same password 1") != hash_password("same password 1")


@pytest.mark.parametrize("stored", ["", "plain", "md5$x$y", "scrypt$a$b$c$d$e", "scrypt$1$2"])
def test_malformed_hash_never_matches(stored: str) -> None:
    assert not verify_password("anything", stored)


def test_check_login() -> None:
    stored = hash_password("a long admin password")
    assert check_login("admin", "a long admin password", "admin", stored)
    assert not check_login("admin", "wrong", "admin", stored)
    assert not check_login("someone", "a long admin password", "admin", stored)


def test_token_round_trip() -> None:
    assert read_token(create_token("admin", KEY, 30), KEY) == "admin"


def test_expired_token_is_rejected() -> None:
    old = create_token("admin", KEY, 30, now=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(InvalidTokenError, match="expired"):
        read_token(old, KEY)


def test_token_signed_with_another_key_is_rejected() -> None:
    with pytest.raises(InvalidTokenError):
        read_token(create_token("admin", "x" * 32, 30), KEY)


def test_unsigned_token_is_rejected() -> None:
    """The classic attack: a token with "alg": "none" and no signature."""
    claims = {"sub": "admin", "iss": "nxcat", "iat": 0, "exp": 9_999_999_999}
    forged = jwt.encode(claims, key="", algorithm="none")
    with pytest.raises(InvalidTokenError):
        read_token(forged, KEY)


def test_token_from_another_issuer_is_rejected() -> None:
    now = datetime.now(UTC)
    other = jwt.encode(
        {"sub": "admin", "iss": "other", "iat": now, "exp": now + timedelta(minutes=5)},
        KEY,
        algorithm="HS256",
    )
    with pytest.raises(InvalidTokenError):
        read_token(other, KEY)


def test_token_without_expiry_is_rejected() -> None:
    forever = jwt.encode({"sub": "admin", "iss": "nxcat", "iat": 0}, KEY, algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        read_token(forever, KEY)


@pytest.mark.parametrize("garbage", ["", "abc", "a.b.c"])
def test_garbage_token_is_rejected(garbage: str) -> None:
    with pytest.raises(InvalidTokenError):
        read_token(garbage, KEY)


def test_cli_prints_a_hash(capsys: pytest.CaptureFixture[str]) -> None:
    main(["--password", "a long admin password"])
    printed = capsys.readouterr().out.strip()
    assert verify_password("a long admin password", printed)


def test_cli_refuses_short_password() -> None:
    with pytest.raises(SystemExit):
        main(["--password", "short"])
