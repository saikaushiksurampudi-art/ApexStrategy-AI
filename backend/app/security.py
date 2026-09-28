"""Password hashing and JWT helpers."""

from __future__ import annotations

import contextlib
import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

from app.config import settings

logger = logging.getLogger(__name__)

# bcrypt silently truncates anything past 72 bytes, which means two different
# long passwords can authenticate the same account. bcrypt_sha256 pre-hashes
# with SHA-256 so the full password always contributes. Plain bcrypt is kept in
# the list so hashes created before this change still verify and are upgraded
# transparently on next login.
pwd_context = CryptContext(
    schemes=["bcrypt_sha256", "bcrypt"],
    deprecated="auto",
    bcrypt_sha256__rounds=12,
)

# A real hash used as a decoy so that authenticating a non-existent account
# costs the same as authenticating a real one. See `verify_password_dummy`.
_DUMMY_HASH = pwd_context.hash("a-password-that-is-never-valid")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(plain, hashed)
    except ValueError:
        return False


def verify_password_dummy(plain: str) -> bool:
    """Burn the same CPU as a real verification, then fail.

    Login must take the same time whether or not the email exists. Without
    this, bcrypt's deliberate slowness becomes an oracle: a fast rejection
    means "no such account", which enumerates the user table.
    """
    with contextlib.suppress(ValueError):
        pwd_context.verify(plain, _DUMMY_HASH)
    return False


def needs_rehash(hashed: str) -> bool:
    """True when a stored hash uses a deprecated scheme or cost."""
    try:
        return pwd_context.needs_update(hashed)
    except ValueError:
        return False


def create_access_token(subject: str, extra: Optional[Dict[str, Any]] = None) -> str:
    now = datetime.now(UTC)
    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a token.

    ``algorithms`` is pinned to the configured algorithm so a token claiming
    ``alg: none`` -- or a different algorithm entirely -- can never be accepted.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError:
        return None
