"""Security middleware: response headers and rate limiting."""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach defensive headers to every response.

    The CSP is deliberately strict but has to accommodate what the app actually
    loads: Google Fonts stylesheets, Wikimedia portraits, and the inline styles
    Recharts writes onto SVG nodes.
    """

    CSP = "; ".join(
        [
            "default-src 'self'",
            "base-uri 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
            "object-src 'none'",
            # Vite injects styles at runtime and Recharts sets inline styles.
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com data:",
            # Driver portraits come from Wikimedia Commons.
            "img-src 'self' data: https://upload.wikimedia.org https://thumb.wikimedia.org",
            "script-src 'self'",
            "connect-src 'self'",
        ]
    )

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        headers = response.headers

        headers.setdefault("X-Content-Type-Options", "nosniff")
        headers.setdefault("X-Frame-Options", "DENY")
        headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        headers.setdefault(
            "Permissions-Policy",
            "geolocation=(), microphone=(), camera=(), payment=(), usb=()",
        )
        headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")

        # The dev server needs a looser CSP than the built bundle: Vite serves
        # modules with inline bootstrapping and opens a websocket for HMR.
        if settings.is_production:
            headers.setdefault("Content-Security-Policy", self.CSP)
            # Only meaningful over HTTPS, which is what App Runner terminates.
            headers.setdefault(
                "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
            )
        else:
            headers.setdefault(
                "Content-Security-Policy-Report-Only", self.CSP
            )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window rate limiting, with a much tighter budget for auth routes.

    This is an in-process limiter: it protects a single instance and resets on
    restart. That is the right scope for this application -- App Runner sits
    behind AWS WAF, which is where distributed limits belong -- but it is a
    meaningful speed bump against the credential-stuffing case, where an
    unlimited endpoint lets an attacker try thousands of passwords a second.
    """

    def __init__(
        self,
        app,
        default_limit: Optional[int] = None,
        auth_limit: Optional[int] = None,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.default_limit = default_limit or settings.rate_limit_per_minute
        self.auth_limit = auth_limit or settings.rate_limit_auth_per_minute
        self.window = window_seconds
        self._hits: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)

    def reset(self) -> None:
        """Clear all counters. Used by tests to isolate cases."""
        self._hits.clear()

    # Endpoints where a guess is worth something to an attacker.
    AUTH_PATHS = ("/auth/login", "/auth/register")

    def _client_key(self, request: Request) -> str:
        # App Runner terminates TLS and forwards the caller in X-Forwarded-For.
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next):
        if not settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        is_auth = any(path.endswith(suffix) for suffix in self.AUTH_PATHS)
        limit = self.auth_limit if is_auth else self.default_limit
        bucket = "auth" if is_auth else "default"

        key = (self._client_key(request), bucket)
        now = time.monotonic()
        hits = self._hits[key]

        while hits and now - hits[0] > self.window:
            hits.popleft()

        if len(hits) >= limit:
            retry_after = int(self.window - (now - hits[0])) + 1
            logger.warning("rate limit hit: %s %s", key[0], path)
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Too many requests. Please wait and try again."
                },
                headers={"Retry-After": str(retry_after)},
            )

        hits.append(now)

        # Keep the dictionary from growing without bound.
        if len(self._hits) > 10_000:
            stale = [k for k, v in self._hits.items() if not v or now - v[-1] > self.window]
            for k in stale:
                del self._hits[k]

        return await call_next(request)
