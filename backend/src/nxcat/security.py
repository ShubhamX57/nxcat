"""Passwords and login tokens.

- Passwords are stored as salted scrypt hashes (Python standard library), so a
  leaked environment file does not reveal the password.
- Tokens are short-lived JWTs signed with HS256. Decoding accepts only HS256,
  which blocks the classic "alg: none" and algorithm-swap attacks.
"""

import argparse
import base64
import getpass
import hashlib
import hmac
import secrets
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

import jwt

ALGORITHM = "HS256"
ISSUER = "nxcat"
# scrypt cost: n=2**14, r=8, p=1 uses about 16 MB and a few tens of milliseconds.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    """Return 'scrypt$n$r$p$salt$hash', safe to keep in an environment variable."""
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=32
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time check of `password` against a `hash_password` result."""
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, _unb64(expected))


# Checked when the username is wrong, so a wrong username takes as long as a wrong
# password and response times do not reveal which usernames exist.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def check_login(username: str, password: str, admin: str, admin_hash: str) -> bool:
    user_ok = hmac.compare_digest(username.encode(), admin.encode())
    password_ok = verify_password(password, admin_hash if user_ok else _DUMMY_HASH)
    return user_ok and password_ok


def create_token(subject: str, key: str, minutes: int, *, now: datetime | None = None) -> str:
    issued = now or datetime.now(UTC)
    claims = {
        "sub": subject,
        "iss": ISSUER,
        "iat": issued,
        "exp": issued + timedelta(minutes=minutes),
    }
    return jwt.encode(claims, key, algorithm=ALGORITHM)


class InvalidTokenError(Exception):
    """The token is missing, malformed, expired, or signed with another key."""


def read_token(token: str, key: str) -> str:
    """Return the token's subject (the username), or raise `InvalidTokenError`."""
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(str(exc)) from exc
    return str(claims["sub"])


def main(argv: Sequence[str] | None = None) -> None:
    """Command line: print a password hash to put in NXCAT_ADMIN_PASSWORD_HASH."""
    parser = argparse.ArgumentParser(description="Hash a password for NXCAT_ADMIN_PASSWORD_HASH.")
    parser.add_argument("--password", help="read from a prompt if not given (recommended)")
    args = parser.parse_args(argv)
    password = args.password or getpass.getpass("Password: ")
    if len(password) < 12:
        parser.error("use a password of at least 12 characters")
    print(hash_password(password))
