# YouTube Subtitle API - Simplified Single Container
FROM python:3.10-slim-bookworm

LABEL maintainer="Infrastructure Team"
LABEL service="youtube-subtitle-api"
LABEL version="1.0.0"

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r apiuser && useradd -r -g apiuser apiuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY --chown=apiuser:apiuser app/ /app/app/

# Create logs directory
RUN mkdir -p /app/logs && chown -R apiuser:apiuser /app/logs

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=10s \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root
USER apiuser

EXPOSE 8000

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
