"""Security primitives: password hashing, JWT tokens, and API-key handling.

Two different hashing strategies are used on purpose:

* **Passwords** are low-entropy and must resist offline brute force, so they use
  Argon2 (slow, salted, memory-hard).
* **API keys** are high-entropy random tokens. They are hashed with SHA-256 so
  ingestion can look a device up by a single indexed equality check instead of
  verifying every row. SHA-256 is appropriate precisely because the input is not
  guessable. Only the hash is ever stored; the plaintext key is shown once.
"""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error

from app.core.config import settings

_password_hasher = PasswordHasher()

API_KEY_PREFIX = "rsk_"


# --- Passwords ---------------------------------------------------------------


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except Argon2Error:
        return False


# --- JWT ---------------------------------------------------------------------


def create_access_token(subject: str | int) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(subject), "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str | None:
    """Return the token subject (user id) or None if invalid/expired."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None
    return payload.get("sub")


# --- API keys ----------------------------------------------------------------


def generate_api_key() -> str:
    """A fresh, URL-safe device API key. Shown to the user exactly once."""
    return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"


def hash_api_key(api_key: str) -> str:
    return hashlib.sha256(api_key.encode()).hexdigest()


def api_key_prefix(api_key: str) -> str:
    """A short, non-secret label so the dashboard can identify a key."""
    return api_key[: len(API_KEY_PREFIX) + 8]
