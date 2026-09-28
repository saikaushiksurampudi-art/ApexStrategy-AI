"""ApexStrategy AI -- FastAPI application entry point.

In production this single service does two jobs: it serves the JSON API under
``/api`` and it serves the compiled React bundle for everything else. That is
what lets the MVP deploy to AWS App Runner as one container.
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.config import settings
from app.database import init_db
from app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.routers import (
    auth,
    chat,
    circuits,
    constructors,
    drivers,
    feedback,
    health,
    predictions,
    races,
    search,
    seasons,
)

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(
    os.getenv("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist")
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s (%s)", settings.app_name, __version__, settings.environment)
    # Refuses to boot on an insecure production configuration.
    settings.validate_runtime_security()
    init_db()

    # Warm the model cache so the first prediction request is not the one that
    # pays the unpickling cost.
    from app.services.prediction import get_model

    bundle = get_model()
    logger.info(
        "Model: %s", bundle.version if bundle else "not trained yet (run scripts.train_model)"
    )
    yield
    logger.info("Shutting down")


app = FastAPI(
    title=settings.app_name,
    version=__version__,
    description=(
        "AI-assisted Formula 1 race strategy analytics. Predictions are "
        "probability estimates derived from historical data, not forecasts."
    ),
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Order matters: middleware added last runs first, so rate limiting rejects a
# flood before any of the heavier work happens.
app.add_middleware(SecurityHeadersMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    # Explicit rather than "*": with credentials allowed, a permissive policy
    # lets any origin make authenticated requests on a signed-in user's behalf.
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

app.add_middleware(RateLimitMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Log the stack trace but never leak internals to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    detail = str(exc) if settings.debug else "Internal server error"
    return JSONResponse(status_code=500, content={"detail": detail})


# --- API routes ------------------------------------------------------------
for module in (
    health,
    auth,
    races,
    seasons,
    drivers,
    constructors,
    circuits,
    predictions,
    chat,
    search,
):
    app.include_router(module.router, prefix=settings.api_prefix)

app.include_router(feedback.router, prefix=settings.api_prefix)
app.include_router(feedback.saved_router, prefix=settings.api_prefix)


# --- Static frontend -------------------------------------------------------
def _mount_frontend() -> None:
    """Serve the built SPA, if it exists, without shadowing the API."""
    if not FRONTEND_DIR.exists():
        logger.info("No frontend build at %s -- running API only", FRONTEND_DIR)

        @app.get("/", include_in_schema=False)
        def api_root() -> dict:
            return {
                "app": settings.app_name,
                "version": __version__,
                "docs": "/api/docs",
                "health": f"{settings.api_prefix}/health",
                "note": "Frontend bundle not built. Run `npm run build` in ./frontend.",
            }

        return

    assets = FRONTEND_DIR / "assets"
    if assets.exists():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    index_file = FRONTEND_DIR / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str) -> FileResponse:
        """Serve real files directly and hand every other path to the SPA router."""
        candidate = (FRONTEND_DIR / full_path).resolve()
        if (
            full_path
            and FRONTEND_DIR.resolve() in candidate.parents
            and candidate.is_file()
        ):
            return FileResponse(candidate)
        return FileResponse(index_file)


_mount_frontend()
