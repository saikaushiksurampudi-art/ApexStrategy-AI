# syntax=docker/dockerfile:1

# =============================================================================
# Stage 1 -- build the React bundle
# =============================================================================
FROM node:22-alpine AS frontend

WORKDIR /build

# Copy manifests first so the dependency layer caches across source changes.
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --no-audit --no-fund

COPY frontend/ ./
RUN npm run build


# =============================================================================
# Stage 2 -- Python runtime, serving both the API and the built frontend
# =============================================================================
FROM python:3.11-slim AS runtime

# PYTHONUNBUFFERED keeps logs flowing to CloudWatch without buffering delays.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    FRONTEND_DIST=/app/frontend/dist

WORKDIR /app

# libpq is needed by psycopg2 at runtime; curl backs the container healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements-postgres.txt

COPY backend/ /app/backend/
COPY --from=frontend /build/dist /app/frontend/dist

# Run as a non-root user.
RUN useradd --create-home --uid 10001 apex \
    && mkdir -p /app/backend/artifacts /app/backend/data \
    && chown -R apex:apex /app
USER apex

WORKDIR /app/backend
ENV PYTHONPATH=/app/backend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

# App Runner supplies $PORT; the shell form expands it.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 2 --proxy-headers
