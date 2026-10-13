"""Login and the token check used by every write endpoint.

Reading data needs no login. Changing data (for now: starting an ingest) needs a
token from POST /api/v1/auth/token. If the server has no admin account or signing
key configured, write actions are switched off and answer 503.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from nxcat import config
from nxcat.security import InvalidTokenError, check_login, create_token, read_token

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# auto_error=False: we raise our own 401 so the message is the same in every case.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token", auto_error=False)

UNAUTHORISED = HTTPException(
    status.HTTP_401_UNAUTHORIZED,
    detail="a valid login token is required",
    headers={"WWW-Authenticate": "Bearer"},
)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - the OAuth2 token type, not a secret
    expires_in: int  # seconds


def _writes_disabled() -> HTTPException:
    return HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="write actions are disabled: no admin account or signing key is configured",
    )


@router.post("/token", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    """Exchange the admin username and password for a short-lived token."""
    key = config.secret_key()
    admin = config.admin_username()
    admin_hash = config.admin_password_hash()
    if key is None or admin is None or admin_hash is None:
        raise _writes_disabled()
    if not check_login(form.username, form.password, admin, admin_hash):
        # One message for a wrong username or a wrong password: no hint which.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="wrong username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    minutes = config.token_minutes()
    return Token(access_token=create_token(admin, key, minutes), expires_in=minutes * 60)


def require_admin(token: Annotated[str | None, Depends(oauth2_scheme)]) -> str:
    """Dependency for write endpoints: returns the username, or answers 401/503."""
    key = config.secret_key()
    admin = config.admin_username()
    if key is None or admin is None or config.admin_password_hash() is None:
        raise _writes_disabled()
    if token is None:
        raise UNAUTHORISED
    try:
        subject = read_token(token, key)
    except InvalidTokenError:
        raise UNAUTHORISED from None
    if subject != admin:  # e.g. the admin account was renamed since the token was made
        raise UNAUTHORISED
    return subject


AdminDep = Annotated[str, Depends(require_admin)]
