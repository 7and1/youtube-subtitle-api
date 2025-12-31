# Multi-stage build for YouTube Subtitle API
# Stage 1: Builder (build wheels, including transitive deps)
FROM python:3.13-slim-bookworm AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel && \
    pip wheel --no-cache-dir --wheel-dir /build/wheels -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim-bookworm

LABEL maintainer="Infrastructure Team"
LABEL service="youtube-subtitles-api"
LABEL version="1.0.0"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -r apiuser && useradd -r -g apiuser apiuser

COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt /app/requirements.txt
RUN pip install --no-index --find-links=/wheels -r /app/requirements.txt && rm -rf /wheels

COPY --chown=apiuser:apiuser src/ /app/src/
COPY --chown=apiuser:apiuser main.py /app/
COPY --chown=apiuser:apiuser config/ /app/config/
COPY --chown=apiuser:apiuser alembic/ /app/alembic/
COPY --chown=apiuser:apiuser alembic.ini /app/alembic.ini

RUN mkdir -p /app/logs /app/tmp && \
    chown -R apiuser:apiuser /app/logs /app/tmp && \
    chmod 755 /app/logs /app/tmp

HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8010/health || exit 1

USER apiuser

EXPOSE 8010

# Use Gunicorn in production; env-driven concurrency & timeouts.
CMD ["sh", "-c", "exec gunicorn -k uvicorn.workers.UvicornWorker -w ${WORKERS:-1} -b ${API_HOST:-0.0.0.0}:${API_PORT:-8010} --timeout ${WORKER_TIMEOUT:-30} --graceful-timeout ${WORKER_TIMEOUT:-30} --access-logfile - --error-logfile - main:app"]
