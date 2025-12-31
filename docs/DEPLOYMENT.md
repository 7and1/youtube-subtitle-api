# YouTube Subtitle API - Deployment Guide

## Prerequisites

Before deploying, ensure you have:

1. **VPS Access**: SSH access to 107.174.42.198 as root
2. **Environment**: Docker, Docker Compose, and Make installed
3. **Dependencies**: Redis and PostgreSQL running on the VPS (shared infrastructure)
4. **Credentials**: Environment variables prepared

## Pre-Deployment Setup

### 1. Create Environment File

Copy `.env.example` to create your production environment file:

```bash
cd /opt/docker-projects/heavy-tasks/YouTube-Subtitle-API

# Copy the example file
cp .env.example .env.production

# Edit with your actual values
nano .env.production
```

#### Required Security Variables

You MUST configure at least one authentication method for admin endpoints:

```bash
# Generate API Key
openssl rand -base64 32
# Output: YOUR_API_KEY_HERE - set as API_KEY=

# Generate JWT Secret (alternative to API key)
openssl rand -base64 32
# Output: YOUR_JWT_SECRET_HERE - set as JWT_SECRET=

# Generate Webhook Secret (if using webhooks)
openssl rand -base64 32
# Output: YOUR_WEBHOOK_SECRET_HERE - set as WEBHOOK_SECRET=
```

#### Required CORS Configuration

The API defaults to denying all CORS requests (fail closed). You MUST configure allowed origins:

```bash
# For specific domains (production)
ALLOWED_ORIGINS=https://example.com,https://www.example.com

# NEVER use "*" in production (allows all origins - dangerous!)
# ALLOWED_ORIGINS=*  # DANGEROUS - only for development
```

### 2. Configure Nginx Reverse Proxy

The service will be auto-discovered by nginx-proxy via docker-compose labels.

To manually configure (if not using auto-discovery):

```nginx
# /etc/nginx/conf.d/youtube-subtitles-api.conf
upstream youtube_api {
    server 127.0.0.1:8010;
}

server {
    listen 80;
    server_name api.youtube-subtitles.com;

    location / {
        proxy_pass http://youtube_api;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts for long-running extraction
        proxy_connect_timeout 30s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

### 3. Database Schema Initialization

```sql
-- Connect to supabase-db as postgres user
psql -h localhost -U postgres -d postgres -c "CREATE SCHEMA IF NOT EXISTS youtube_subtitles;"
```

## Deployment

### Step 1: Backup Database (Existing Deployments)

```bash
# Backup before any deployment
cd /opt/docker-projects/heavy-tasks/YouTube-Subtitle-API
pg_dump -h supabase-db -U postgres -n youtube_subtitles > backup_$(date +%Y%m%d_%H%M%S).sql
```

### Step 2: Build Docker Images

```bash
cd /opt/docker-projects/heavy-tasks/YouTube-Subtitle-API

# Build API and Worker images
make build

# Verify images were created
docker images | grep youtube-subtitles
```

### Step 3: Validate Configuration

```bash
# Validate docker-compose.yml
make validate

# Check environment variables are loaded
docker-compose config
```

### Step 4: Run Database Migrations

```bash
# Run Alembic migrations to ensure schema is up to date
docker-compose run --rm api alembic upgrade head

# Verify current migration
docker-compose run --rm api alembic current
```

### Step 5: Deploy Services

```bash
# Deploy API and worker instances
make deploy

# Verify containers are running
make ps

# Expected output:
# CONTAINER ID   IMAGE                                  STATUS
# abc123...      heavy-youtube-subtitles-api:latest    Up 10 seconds (healthy)
# def456...      heavy-youtube-subtitles-worker:latest Up 15 seconds
```

### Step 6: Verify Health

```bash
# Health check (should return 200)
curl http://localhost:8010/health

# Expected response:
# {
#   "status": "healthy",
#   "components": {
#     "api": "ready",
#     "redis": "connected",
#     "postgres": "connected"
#   }
# }
```

### Step 7: Check Logs

```bash
# Stream logs from all containers
make logs

# View only API logs
docker-compose logs -f api

# View only worker logs
docker-compose logs -f worker
```

## Post-Deployment Verification

### Test API Endpoints

```bash
# Test subtitle extraction (requires API key if configured)
curl -X POST http://localhost:8010/api/v1/subtitles \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# Expected behavior:
# - Cache hit: HTTP 200 with result
# - Cache miss: HTTP 202 with {job_id}, then poll /api/v1/job/{job_id}

# Get cached subtitles
curl http://localhost:8010/api/v1/subtitles/dQw4w9WgXcQ

# Admin endpoints (require authentication)
curl -X POST http://localhost:8010/api/v1/admin/cache/clear \
  -H "X-API-Key: YOUR_API_KEY"
```

### Verify Authentication

Admin endpoints REQUIRE authentication. Test without auth first:

```bash
# Should fail with 500 or 401
curl -X POST http://localhost:8010/api/v1/admin/cache/clear

# Should succeed with valid API key
curl -X POST http://localhost:8010/api/v1/admin/cache/clear \
  -H "X-API-Key: YOUR_API_KEY"
```

### Test Webhook Integration (Optional)

If using webhooks for job completion notifications:

```bash
# Request extraction with webhook callback
curl -X POST http://localhost:8010/api/v1/subtitles \
  -H "Content-Type: application/json" \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "webhook_url": "https://your-domain.com/webhook"
  }'
```

Webhook payload structure:

```json
{
  "event": "job.completed",
  "job_id": "abc123",
  "video_id": "dQw4w9WgXcQ",
  "status": "success",
  "result": {
    "subtitles": [...]
  },
  "timestamp": "2025-12-31T12:00:00Z"
}
```

Headers included:

- `X-Webhook-Signature`: HMAC SHA256 signature (if WEBHOOK_SECRET configured)
- `X-Webhook-Timestamp`: ISO timestamp for replay protection

### Monitor Resource Usage

```bash
# View container resource usage
make stats

# Monitor specific container
docker stats heavy-youtube-subtitles-api

# Expected CPU/Memory (at idle):
# API: <5% CPU, 150-200MB RAM
# Worker: <1% CPU, 180-250MB RAM per instance
```

## Migrations

### New Deployment

For new deployments, run migrations after deploy:

```bash
docker-compose run --rm api alembic upgrade head
```

### Existing Deployment Upgrade

For existing deployments, the migration sequence is:

1. `20251230_0001_init.py` - Initial schema (subtitle_records, extraction_jobs)
2. `20251231_0002_add_webhook_support.py` - Adds webhook columns

To check current version:

```bash
docker-compose run --rm api alembic current
```

To rollback one migration:

```bash
docker-compose run --rm api alembic downgrade -1
```

## Scaling

### Increase Worker Count

```bash
# Scale to 4 workers
make scale WORKERS=4

# Verify
make ps

# Expected: 1 api + 4 worker containers running
```

### Horizontal Scaling (Multiple VPS)

For multi-VPS deployment:

```bash
# On VPS 2 (different machine):
cd /opt/docker-projects/heavy-tasks/YouTube-Subtitle-API

# Deploy with same environment and shared Redis/PostgreSQL
make deploy

# Workers will automatically connect to shared queue
```

## Frontend (Cloudflare Pages)

This repo includes a separate frontend in `frontend/` intended to be deployed to Cloudflare Pages.

Recommended approach: proxy backend routes via Pages Functions.

- Pages build settings:
  - Root directory: `frontend`
  - Build command: `npm run build`
  - Output directory: `dist`
- Pages environment variables:
  - `BACKEND_BASE_URL` (required): `https://api.your-domain.com`
  - `BACKEND_API_KEY` (optional): injected as `X-API-Key` by the proxy

Proxied paths (same-origin on the Pages site):

- `/api/*`, `/docs/*`, `/openapi.json`, `/health`, `/metrics`

## Monitoring & Observability

### View Metrics

```bash
# Prometheus metrics endpoint
curl http://localhost:8010/metrics | grep youtube_

# Key metrics:
# - http_requests_total (by status, method)
# - http_request_duration_seconds (latency histogram)
# - youtube_extraction_duration_seconds (extraction time)
# - youtube_cache_hits_total (cache performance)
# - job_queue_depth (RQ queue size)
```

### View Logs

```bash
# JSON structured logs (useful for log aggregation)
docker-compose logs api | jq '.message'

# Filter by level
docker-compose logs api | jq 'select(.level == "ERROR")'

# Extract specific fields
docker-compose logs api | jq '{timestamp, level, video_id, duration_ms}'
```

### Check Queue Status

```bash
# View job queue depth
make admin-queue-stats

# Get rate limit stats for IP
curl "http://localhost:8010/api/v1/admin/rate-limit/stats/1.2.3.4" \
  -H "X-API-Key: YOUR_API_KEY"
```

## Maintenance

### Update Service

```bash
# 1. Backup database
pg_dump -h supabase-db -U postgres -n youtube_subtitles > backup.sql

# 2. Pull latest code
git pull origin main

# 3. Rebuild images
make build

# 4. Run migrations (if any)
docker-compose run --rm api alembic upgrade head

# 5. Deploy (zero-downtime with rolling restart)
make deploy

# 6. Verify health
make health
```

### Cache Management

```bash
# Clear specific video cache
curl -X DELETE "http://localhost:8010/api/v1/admin/cache/clear/dQw4w9WgXcQ" \
  -H "X-API-Key: YOUR_API_KEY"

# Clear all cache
curl -X POST "http://localhost:8010/api/v1/admin/cache/clear" \
  -H "X-API-Key: YOUR_API_KEY"

# Clear Redis cache directly
redis-cli -n 2 FLUSHDB
```

### Log Rotation

Configured in docker-compose.yml:

```yaml
logging:
  options:
    max-size: "20m" # Rotate at 20MB
    max-file: "3" # Keep 3 old files (60MB total)
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs for error
docker-compose logs api

# Common issues:
# - Port 8010 already in use: netstat -tlnp | grep 8010
# - Redis not running: docker ps | grep redis
# - Database connection failed: verify DB_PASSWORD in .env.production
# - Missing authentication: verify API_KEY or JWT_SECRET is set
```

### Admin Endpoints Return 500

This means authentication is not configured. Admin endpoints fail closed:

```bash
# Check if API_KEY is set
docker-compose exec api env | grep API_KEY

# Check if JWT_SECRET is set
docker-compose exec api env | grep JWT_SECRET

# At least one must be configured for admin access
```

### CORS Errors in Frontend

```bash
# Check ALLOWED_ORIGINS setting
docker-compose exec api env | grep ALLOWED_ORIGINS

# Should be specific domains, not empty
# Example: ALLOWED_ORIGINS=https://example.com
```

### High Memory Usage

```bash
# Check memory per process
docker stats heavy-youtube-subtitles-api

# Better: reduce WORKERS or increase machine RAM
# Edit .env.production: WORKERS=1
```

### Worker Jobs Not Processing

```bash
# Check job queue
redis-cli -n 2 LLEN youtube-extraction

# Check worker logs
docker-compose logs worker

# Restart workers
docker-compose restart worker
```

### Webhook Delivery Failures

```bash
# Check worker logs for webhook errors
docker-compose logs worker | grep webhook

# Verify WEBHOOK_SECRET is set if signatures are required
docker-compose exec api env | grep WEBHOOK_SECRET

# Check webhook_url format (must be http or https)
```

## Security Configuration

### Required Authentication

Admin endpoints REQUIRE at least one authentication method:

| Method  | Environment Variable | Header Format                 |
| ------- | -------------------- | ----------------------------- |
| API Key | `API_KEY`            | `X-API-Key: your-key`         |
| JWT     | `JWT_SECRET`         | `Authorization: Bearer token` |

If neither is configured, admin endpoints will return HTTP 500 with a clear error message.

### CORS Configuration

- Default: Empty list (DENY ALL)
- Production: Set specific origins
- Development: `*` (wildcard - dangerous in production)

### Rate Limiting

- Default: 30 requests/minute per IP
- Configurable via `RATE_LIMIT_REQUESTS_PER_MINUTE`
- Fails closed by default (`RATE_LIMIT_FAIL_OPEN=false`)

## Rollback

If deployment fails:

```bash
# 1. Get previous image tag
docker images | grep youtube-subtitles

# 2. Tag current as backup
docker tag heavy-youtube-subtitles-api:latest heavy-youtube-subtitles-api:backup-$(date +%Y%m%d)

# 3. Stop current containers
docker-compose down

# 4. Edit docker-compose.yml to use previous tag
# Or rollback git: git reset --hard HEAD~1

# 5. Rebuild and redeploy
make build
make deploy

# 6. Verify health
make health
```

## Disaster Recovery

### Backup Database

```bash
# Full backup of youtube_subtitles schema
pg_dump -h supabase-db -U postgres -n youtube_subtitles > backup_$(date +%Y%m%d).sql

# Restore
psql -h supabase-db -U postgres -d postgres < backup_20251230.sql
```

### Rebuild Cache

```bash
# Cache is ephemeral, can be safely cleared
redis-cli -n 2 FLUSHDB

# Subtitles will be re-extracted on next request
```

### Full Reset (if corrupted state)

```bash
# WARNING: Destructive operation
make down
# Note: docker-compose down -v would delete volumes - DO NOT USE with bind mounts
rm -rf logs/*

# Then redeploy
make deploy
```

## Production Checklist

For a complete production deployment checklist, see `docs/PRODUCTION_CHECKLIST.md`.

Quick checklist:

- [ ] Environment variables configured with actual secrets
- [ ] API_KEY or JWT_SECRET configured (required for admin)
- [ ] ALLOWED_ORIGINS set to specific domains
- [ ] Database schema initialized
- [ ] Redis connected and accessible
- [ ] Health check passing (200 OK)
- [ ] Logs streaming without errors
- [ ] Rate limiting configured
- [ ] Monitoring alerts set up
- [ ] Backup strategy tested
- [ ] Load testing completed

---

**Last Updated**: 2025-12-31
**Maintainer**: Infrastructure Team
