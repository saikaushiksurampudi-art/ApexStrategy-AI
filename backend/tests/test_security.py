"""Security regression tests.

Each test here corresponds to a finding from the security audit. They exist so
a fix cannot be silently undone by a later refactor.
"""

from __future__ import annotations

import time

import pytest

from app.config import DEV_JWT_SECRET, Settings
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    needs_rehash,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
def test_long_passwords_are_not_truncated():
    """bcrypt truncates at 72 bytes; two long passwords must not collide.

    Before the fix, any password sharing its first 72 bytes authenticated the
    same account.
    """
    base = "A" * 72
    correct = base + "aaaaaaaaaa"
    attacker = base + "bbbbbbbbbb"

    stored = hash_password(correct)
    assert verify_password(correct, stored) is True
    assert verify_password(attacker, stored) is False


def test_hashes_use_the_prehashing_scheme():
    assert hash_password("a-normal-password").startswith("$bcrypt-sha256$")


def test_legacy_bcrypt_hashes_still_verify_and_are_flagged():
    """Existing accounts must keep working, and be upgraded on next login."""
    from passlib.hash import bcrypt

    legacy = bcrypt.hash("legacy-password")
    assert verify_password("legacy-password", legacy) is True
    assert needs_rehash(legacy) is True


def test_verify_rejects_malformed_hash():
    assert verify_password("anything", "not-a-hash") is False


# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------
def test_tampered_token_is_rejected():
    token = create_access_token("1")
    assert decode_access_token(token) is not None
    assert decode_access_token(token.rsplit(".", 1)[0] + ".forged") is None
    assert decode_access_token("garbage") is None
    assert decode_access_token("") is None


def test_token_signed_with_another_key_is_rejected():
    import jwt as pyjwt

    forged = pyjwt.encode({"sub": "1", "exp": 9999999999}, "attacker-key", algorithm="HS256")
    assert decode_access_token(forged) is None


def test_unsigned_alg_none_token_is_rejected():
    """The classic JWT bypass: claim alg=none and drop the signature."""
    import base64
    import json

    def b64(data: dict) -> str:
        raw = json.dumps(data).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    forged = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': '1', 'exp': 9999999999})}."
    assert decode_access_token(forged) is None


def test_expired_token_is_rejected(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "access_token_expire_minutes", -1)
    assert decode_access_token(create_access_token("1")) is None


# ---------------------------------------------------------------------------
# Configuration guards
# ---------------------------------------------------------------------------
def test_production_refuses_the_default_jwt_secret():
    settings = Settings(_env_file=None, environment="production", jwt_secret=DEV_JWT_SECRET)
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        settings.validate_runtime_security()


def test_production_refuses_a_short_jwt_secret():
    settings = Settings(_env_file=None, environment="production", jwt_secret="tooshort")
    with pytest.raises(RuntimeError, match="at least 32"):
        settings.validate_runtime_security()


def test_production_refuses_debug_mode():
    settings = Settings(
        _env_file=None, environment="production", jwt_secret="x" * 48, debug=True
    )
    with pytest.raises(RuntimeError, match="DEBUG"):
        settings.validate_runtime_security()


def test_production_refuses_wildcard_cors():
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="x" * 48,
        debug=False,
        cors_origins=["*"],
    )
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        settings.validate_runtime_security()


def test_valid_production_config_passes():
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="x" * 48,
        debug=False,
        cors_origins=["https://apex.example.com"],
        database_url="postgresql+psycopg2://u:p@host/db",
    )
    settings.validate_runtime_security()  # must not raise


def test_debug_defaults_to_false():
    """An unset DEBUG must never leak exception text."""
    assert Settings(_env_file=None).debug is False


# ---------------------------------------------------------------------------
# Endpoint behaviour
# ---------------------------------------------------------------------------
def test_login_does_not_leak_which_emails_exist(client):
    """Unknown and known accounts must fail the same way, at a similar cost."""
    client.post(
        "/api/auth/register",
        json={"email": "real@example.com", "password": "correct-horse-1"},
    )

    def timed(email: str) -> float:
        samples = []
        for _ in range(3):
            started = time.perf_counter()
            response = client.post(
                "/api/auth/login", json={"email": email, "password": "wrong-password-1"}
            )
            samples.append(time.perf_counter() - started)
            assert response.status_code == 401
            assert response.json()["detail"] == "Incorrect email or password"
        return sorted(samples)[1]

    known = timed("real@example.com")
    unknown = timed("nobody@example.com")

    # Before the fix this ratio was ~160x. Allow generous headroom for CI noise
    # while still catching a regression to "skip hashing when absent".
    ratio = max(known, unknown) / max(min(known, unknown), 1e-9)
    assert ratio < 10, f"login timing differs by {ratio:.1f}x -- enumerable"


def test_security_headers_are_present(client):
    response = client.get("/api/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Referrer-Policy" in response.headers
    assert "Permissions-Policy" in response.headers


def test_prediction_writes_require_authentication(client):
    """Persisting predictions must not be reachable by an anonymous GET."""
    response = client.post("/api/predictions/race/1/snapshot")
    assert response.status_code == 401


def test_get_predictions_does_not_accept_a_persist_flag(client):
    """The old `?persist=true` write-via-GET must be gone."""
    from app.models import Prediction

    response = client.get("/api/predictions/next?persist=true")
    assert response.status_code in (200, 404)
    # Whatever it returned, nothing may have been written.
    from sqlalchemy import select

    from app.database import get_db  # noqa: F401

    # The overridden session is the same one the fixture seeded.
    session = next(iter(client.app.dependency_overrides.values()))()
    assert session.scalars(select(Prediction)).all() == []


def test_path_traversal_is_blocked(client):
    """The SPA catch-all must never serve a file outside the bundle."""
    for attempt in (
        "../../../../etc/passwd",
        "assets/../../../../etc/passwd",
        "%2e%2e/%2e%2e/etc/passwd",
    ):
        response = client.get(f"/{attempt}")
        assert "root:" not in response.text


def test_sql_injection_does_not_execute(client):
    """The ORM parameterises everything; payloads are treated as literals."""
    before = client.get("/api/health").json()["database"]["drivers"]
    for payload in ("' OR '1'='1", "'; DROP TABLE drivers;--", "%' OR 1=1--"):
        client.get("/api/search", params={"q": payload})
        client.get("/api/drivers/compare", params={"a": payload, "b": "bolt"})
    after = client.get("/api/health").json()["database"]["drivers"]
    assert after == before


def test_oversized_input_is_rejected(client):
    assert client.post("/api/chat", json={"question": "a" * 100_000}).status_code == 422
    assert (
        client.post(
            "/api/feedback",
            json={"surface": "chat", "rating": "helpful", "comment": "a" * 500_000},
        ).status_code
        == 422
    )


def test_user_cannot_touch_another_users_saved_comparison(client):
    first = client.post(
        "/api/auth/register", json={"email": "one@example.com", "password": "password-one-1"}
    ).json()
    second = client.post(
        "/api/auth/register", json={"email": "two@example.com", "password": "password-two-1"}
    ).json()

    headers_one = {"Authorization": f"Bearer {first['access_token']}"}
    headers_two = {"Authorization": f"Bearer {second['access_token']}"}

    saved = client.post(
        "/api/saved",
        headers=headers_one,
        json={"label": "private", "kind": "driver", "payload": {}},
    ).json()

    assert client.get("/api/saved", headers=headers_two).json() == []
    assert client.delete(f"/api/saved/{saved['id']}", headers=headers_two).status_code == 404
    assert len(client.get("/api/saved", headers=headers_one).json()) == 1


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
def test_auth_endpoints_are_rate_limited(client, monkeypatch):
    """Unlimited login attempts make credential stuffing free.

    Rate limiting is disabled for the rest of the suite (see conftest), so this
    test turns it on explicitly rather than depending on global state.
    """
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_auth_per_minute", 5)

    codes = [
        client.post(
            "/api/auth/login",
            json={"email": f"brute{i}@example.com", "password": "guessing-1"},
        ).status_code
        for i in range(12)
    ]

    assert 429 in codes, "auth endpoint accepted unlimited attempts"
    assert codes[0] == 401, "the first attempt should be a normal failure"
    # Everything after the limit must be refused.
    assert codes[-1] == 429


def test_rate_limited_response_tells_the_client_when_to_retry(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    monkeypatch.setattr(settings, "rate_limit_auth_per_minute", 2)

    last = None
    for _ in range(6):
        last = client.post(
            "/api/auth/login", json={"email": "x@example.com", "password": "guessing-1"}
        )
    assert last is not None and last.status_code == 429
    assert "Retry-After" in last.headers
    assert int(last.headers["Retry-After"]) > 0


def test_ordinary_browsing_is_not_rate_limited(client, monkeypatch):
    """The default budget must not interfere with normal dashboard use."""
    from app.config import settings

    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    codes = [client.get("/api/health").status_code for _ in range(40)]
    assert set(codes) == {200}
