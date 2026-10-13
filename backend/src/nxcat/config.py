"""Settings read from environment variables.

Secrets (the signing key and the admin password hash) are never given defaults
in code: if they are not set, write actions are switched off, rather than
running with a guessable secret.
"""

import os
from pathlib import Path

DEFAULT_DATABASE_URL = "postgresql+psycopg://nxcat:nxcat@localhost:5432/nxcat"
MIN_SECRET_KEY_LENGTH = 32


def database_url() -> str:
    """Database to use. Set NXCAT_DATABASE_URL to override the local default."""
    return os.environ.get("NXCAT_DATABASE_URL", DEFAULT_DATABASE_URL)


def data_root() -> Path:
    """The only folder (and its subfolders) that the ingest endpoint may read."""
    return Path(os.environ.get("NXCAT_DATA_ROOT", "/data"))


def secret_key() -> str | None:
    """Key that signs login tokens. None (writes disabled) if missing or too short."""
    key = os.environ.get("NXCAT_SECRET_KEY", "")
    return key if len(key) >= MIN_SECRET_KEY_LENGTH else None


def admin_username() -> str | None:
    return os.environ.get("NXCAT_ADMIN_USERNAME") or None


def admin_password_hash() -> str | None:
    """Output of `nxcat-hash-password`. The plain password is never stored."""
    return os.environ.get("NXCAT_ADMIN_PASSWORD_HASH") or None


def token_minutes() -> int:
    return int(os.environ.get("NXCAT_TOKEN_MINUTES", "30"))


def llm_model() -> str | None:
    """LiteLLM model name, e.g. "ollama/qwen2.5:7b-instruct". None switches /search/ask off."""
    return os.environ.get("NXCAT_LLM_MODEL") or None


def llm_api_base() -> str | None:
    """Where the model server is, e.g. http://host.docker.internal:11434 for Ollama on a Mac."""
    return os.environ.get("NXCAT_LLM_API_BASE") or None


def llm_timeout() -> float:
    return float(os.environ.get("NXCAT_LLM_TIMEOUT", "30"))
