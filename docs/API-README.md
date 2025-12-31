# YouTube Subtitle API - Production Deployment

**Status:** Ready for Implementation
**Version:** 1.0.0
**Deployment:** Heavy-Tasks Zone on VPS 107.174.42.198

## Overview

This is a production-grade YouTube subtitle extraction API designed for large-scale distributed deployment. The architecture uses async task processing to handle extraction latency gracefully, with intelligent 3-tier caching and rate limiting.

### Core Features

- **Dual-Engine Extraction**: youtube-transcript-api (primary) + yt-dlp (fallback)
- **Async Processing**: Non-blocking API with worker queue (RQ + Redis)
- **Webhook Notifications**: Optional callbacks on job completion with HMAC signatures
- **3-Tier Caching**: In-memory (5min) → Redis (24h) → PostgreSQL (30d)
- **Rate Limiting**: Token bucket (30 req/min per IP)
- **Production Ready**: Structured logging, health checks, metrics, error handling
- **Cost Efficient**: ~$20/month on shared VPS, scales horizontally

## Quick Start (5 minutes)

```bash
cd /opt/docker-projects/heavy-tasks/YouTube-Subtitle-API

# 1. Initialize (validates dependencies)
chmod +x init.sh && ./init.sh

# 2. Configure environment
nano .env.production  # Update DB_PASSWORD and JWT_SECRET

# 3. Build and deploy
make build
make deploy

# 4. Verify health
make health
```

For detailed setup: See **QUICK_START.md**

## Documentation Index

| Document                  | Purpose                              | Length      |
| ------------------------- | ------------------------------------ | ----------- |
| **QUICK_START.md**        | 5-minute setup guide                 | 5 min read  |
| **ARCHITECTURE.md**       | Complete technical specification     | 30 min read |
| **DEPLOYMENT.md**         | Step-by-step deployment instructions | 20 min read |
| **DEPLOYMENT_SUMMARY.md** | Executive overview with diagrams     | 25 min read |
| **README.md**             | This file - Overview and structure   | 10 min read |

## Architecture at a Glance

```
Request → FastAPI (8010) → Rate Limit Check
                        ↓
                    Cache Hit? → Return (cached)
                        ↓
                   Enqueue Job → Redis Queue
                        ↓
          Worker Extracts (parallel) → YouTube API
                        ↓
           Save to PostgreSQL → Update Caches
                        ↓
            Client polls /api/job/{id} → Result Ready
```

**Key Advantages:**

- API responds in <10ms (immediate queue confirmation)
- Extraction happens in parallel (scale workers independently)
- Results cached for future requests (avoid re-extraction)
- Graceful YouTube API handling (fallback on 403/429)

## Project Structure

```
/opt/docker-projects/heavy-tasks/YouTube-Subtitle-API/
├── Dockerfile                 # Multi-stage build (API)
├── Dockerfile.worker          # Worker container
├── docker-compose.yml         # Service orchestration
├── Makefile                   # Operational commands
├── requirements.txt           # Python dependencies (pinned)
├── init.sh                    # Automated initialization
├── main.py                    # FastAPI application
│
├── src/
│   ├── api/
│   │   └── routes/
│   │       ├── health.py      # Health checks
│   │       ├── subtitles.py   # Subtitle endpoints
│   │       └── admin.py       # Admin/monitoring
│   ├── services/
│   │   ├── cache.py           # Redis caching
│   │   ├── database.py        # PostgreSQL async driver
│   │   └── rate_limiter.py    # Token bucket rate limiting
│   ├── models/
│   │   └── subtitle.py        # SQLAlchemy ORM
│   └── core/
│       ├── config.py          # Pydantic settings
│       └── logging_config.py  # Structured logging
│
├── ARCHITECTURE.md            # Technical design (complete)
├── DEPLOYMENT.md              # Deployment guide (step-by-step)
├── DEPLOYMENT_SUMMARY.md      # Executive summary (with diagrams)
├── QUICK_START.md             # Quick start (5 minutes)
├── README.md                  # This file
└── .gitignore                 # Git ignore rules
```

## Technology Stack

### Core

- **FastAPI 0.115.5** - Async web framework
- **Uvicorn 0.32.0** - ASGI production server
- **Gunicorn 23.0.0** - Multi-worker support

### YouTube Integration

- **youtube-transcript-api 0.6.1** - Primary extractor (fast, cached)
- **yt-dlp 2025.1.1** - Fallback extractor (handles restrictions)

### Database & Caching

- **PostgreSQL** (Supabase) - Persistent subtitle storage
- **Redis** - Job queue, distributed cache, rate limiting
- **SQLAlchemy 2.0.35** - Async ORM

### Async & Queue

- **RQ 1.15.1** - Redis job queue
- **asyncpg 0.29.0** - PostgreSQL async driver
- **redis-py asyncio** (`redis[hiredis]`) - Redis async client

### Observability

- **structlog 24.4.0** - Structured JSON logging
- **Prometheus** - Metrics collection
- **python-json-logger** - CloudLogging compatible format

**Base Image:** python:3.13-slim-bookworm (150MB, secure, optimal performance)

## API Endpoints

### Base URL

```
https://api.example.com
```

### API Versioning

| Version | Status  | Path Prefix | Deprecated |
| ------- | ------- | ----------- | ---------- |
| v1      | Current | `/api/v1/`  | No         |
| (none)  | Legacy  | `/api/`     | Yes        |

**Note:** Legacy `/api/` paths automatically redirect to `/api/v1/` with HTTP 308.

### Core Extraction

#### POST /api/v1/subtitles

Extract subtitles for a YouTube video. Returns cached result immediately if available, or queues an extraction job.

**Request Headers:**

| Header       | Type   | Required    | Description                        |
| ------------ | ------ | ----------- | ---------------------------------- |
| Content-Type | string | Yes         | Must be `application/json`         |
| X-API-Key    | string | Conditional | Required if authentication enabled |
| X-Request-ID | string | No          | Custom request ID for tracing      |

**Request Body:**

| Field        | Type    | Required | Default | Description                                 |
| ------------ | ------- | -------- | ------- | ------------------------------------------- |
| video_url    | string  | No\*     | -       | Full YouTube URL                            |
| video_id     | string  | No\*     | -       | 11-character YouTube video ID               |
| language     | string  | No       | `en`    | Language code (e.g., `en`, `es`, `zh-Hans`) |
| clean_for_ai | boolean | No       | `true`  | Normalize text for AI processing            |
| webhook_url  | string  | No       | -       | URL for async completion notification       |

\*Either `video_url` or `video_id` is required.

**Response 200 (Cached):**

```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Never Gonna Give You Up",
  "language": "en",
  "extraction_method": "youtube-transcript-api",
  "subtitle_count": 150,
  "duration_ms": 1234,
  "subtitles": [
    { "text": "Never gonna give you up", "start": 1.5, "duration": 2.0 }
  ],
  "plain_text": "Full transcript...",
  "cached": true,
  "cache_tier": "redis",
  "created_at": "2025-12-31T00:00:00Z"
}
```

**Response 202 (Queued):**

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "queued",
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "webhook_url": "https://your-app.com/webhook"
}
```

**Rate Limited:** 30 requests/minute per IP (including burst)

---

#### GET /api/v1/subtitles/{video_id}

Get cached subtitles for a video. Does not trigger extraction if not cached.

**Path Parameters:**

| Parameter | Type   | Description                   |
| --------- | ------ | ----------------------------- |
| video_id  | string | 11-character YouTube video ID |

**Query Parameters:**

| Parameter | Type   | Required | Default |
| --------- | ------ | -------- | ------- |
| language  | string | No       | `en`    |

**Response 200:** Same as POST /api/v1/subtitles cached response

**Response 404:** Subtitles not found in cache

---

#### POST /api/v1/subtitles/batch

Request batch subtitle extraction for multiple videos. Cached results returned immediately; others queued.

**Request Body:**

| Field        | Type    | Required | Default | Description                  |
| ------------ | ------- | -------- | ------- | ---------------------------- |
| video_ids    | array   | Yes      | -       | Array of video IDs (max 100) |
| language     | string  | No       | `en`    | Language code                |
| clean_for_ai | boolean | No       | `true`  | Normalize text for AI        |
| webhook_url  | string  | No       | -       | URL for notifications        |

**Response 202:**

```json
{
  "status": "queued",
  "video_count": 10,
  "queued_count": 7,
  "cached_count": 3,
  "job_ids": ["job1", "job2", "..."],
  "cached": ["video1", "video2", "video3"]
}
```

---

#### GET /api/v1/job/{job_id}

Get the status of an asynchronous subtitle extraction job.

**Path Parameters:**

| Parameter | Type   | Description               |
| --------- | ------ | ------------------------- |
| job_id    | string | Job ID from POST response |

**Response (Queued/Processing):**

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "queued",
  "enqueued_at": "2025-12-31T00:00:00Z",
  "ended_at": null,
  "result": null,
  "exc_info": null
}
```

**Response (Finished):**

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "finished",
  "enqueued_at": "2025-12-31T00:00:00Z",
  "ended_at": "2025-12-31T00:00:05Z",
  "result": {
    "success": true,
    "video_id": "dQw4w9WgXcQ",
    "subtitles": [...]
  },
  "exc_info": null
}
```

**Response (Failed):**

```json
{
  "job_id": "abc123-def456-ghi789",
  "status": "failed",
  "exc_info": "Video unavailable or subtitles disabled"
}
```

---

### Health & Monitoring

#### GET /health

Service health check for load balancers and orchestrators.

**Response 200 (Healthy):**

```json
{
  "status": "healthy",
  "timestamp": "2025-12-31T00:00:00Z",
  "api_version": "v1",
  "components": {
    "api": "ready",
    "redis": "connected",
    "postgres": "connected"
  },
  "memory_cache": {
    "size": 150,
    "hit_rate": 0.85,
    "hits": 1000,
    "misses": 176
  }
}
```

**Response 503 (Degraded):** Returns 503 when any component is disconnected.

---

#### GET /live

Liveness probe for Kubernetes. Returns immediately if process is running.

**Response 200:**

```json
{
  "status": "ok"
}
```

---

#### GET /status

Get detailed service status including version and environment.

**Response 200:**

```json
{
  "service": "youtube-subtitles-api",
  "version": "1.0.0",
  "api_version": "v1",
  "environment": "production",
  "timestamp": "2025-12-31T00:00:00Z"
}
```

---

#### GET /metrics

Prometheus metrics endpoint (only if PROMETHEUS_ENABLED=true).

**Response:** Prometheus text format metrics

---

### Admin Operations

All admin endpoints require authentication. See Authentication section below.

#### POST /api/v1/admin/cache/clear

Clear in-memory and Redis cache. Optionally purge database records.

**Query Parameters:**

| Parameter | Type    | Required | Default | Description                  |
| --------- | ------- | -------- | ------- | ---------------------------- |
| purge_db  | boolean | No       | `false` | Also delete database records |

**Response 200:**

```json
{
  "status": "cleared",
  "message": "Cache cleared",
  "purge_db": false,
  "deleted_db_records": 0,
  "timestamp": "2025-12-31T00:00:00Z"
}
```

---

#### DELETE /api/v1/admin/cache/clear/{video_id}

Clear cache for a specific video.

**Path Parameters:**

| Parameter | Type   | Description       |
| --------- | ------ | ----------------- |
| video_id  | string | Video ID to clear |

**Query Parameters:**

| Parameter | Type   | Required | Default | Description                                   |
| --------- | ------ | -------- | ------- | --------------------------------------------- |
| language  | string | No       | -       | Clear only this language (omits to clear all) |

**Response 200:**

```json
{
  "status": "deleted",
  "video_id": "dQw4w9WgXcQ",
  "language": null,
  "timestamp": "2025-12-31T00:00:00Z"
}
```

---

#### GET /api/v1/admin/queue/stats

Get job queue statistics.

**Response 200:**

```json
{
  "queue_name": "youtube-extraction",
  "queue_depth": 5,
  "active_jobs": 2,
  "failed_jobs": 0,
  "worker_count": 2,
  "timestamp": "2025-12-31T00:00:00Z"
}
```

---

#### GET /api/v1/admin/rate-limit/stats/{client_ip}

Get rate limit statistics for a specific client IP.

**Path Parameters:**

| Parameter | Type   | Description       |
| --------- | ------ | ----------------- |
| client_ip | string | Client IP address |

**Response 200:**

```json
{
  "client_ip": "192.168.1.100",
  "endpoints": {
    "a3f5c9e1": {
      "remaining": 25,
      "reset_in_seconds": 45
    }
  },
  "timestamp": "2025-12-31T00:00:00Z"
}
```

---

#### POST /api/v1/admin/rate-limit/reset/{client_ip}

Reset rate limit for a specific client IP.

**Response 200:**

```json
{
  "status": "reset",
  "client_ip": "192.168.1.100",
  "message": "Rate limit reset for 192.168.1.100",
  "timestamp": "2025-12-31T00:00:00Z"
}
```

---

### Deprecated Endpoints

The following endpoints are maintained for backward compatibility but will be removed in a future version:

| Deprecated                  | Current (v1)                   | Status         |
| --------------------------- | ------------------------------ | -------------- |
| POST /api/subtitles         | POST /api/v1/subtitles         | Auto-redirects |
| POST /api/rewrite-video     | POST /api/v1/subtitles         | Auto-redirects |
| GET /api/subtitles/{id}     | GET /api/v1/subtitles/{id}     | Auto-redirects |
| POST /api/subtitles/batch   | POST /api/v1/subtitles/batch   | Auto-redirects |
| GET /api/job/{id}           | GET /api/v1/job/{id}           | Auto-redirects |
| POST /api/admin/cache/clear | POST /api/v1/admin/cache/clear | Auto-redirects |

## Webhook Support

### Overview

The API supports optional webhook notifications for async job completion. Instead of polling the `/api/job/{job_id}` endpoint, you can provide a `webhook_url` when creating a job, and the API will send a POST request to your endpoint when the job completes.

### Configuration

Set the `WEBHOOK_SECRET` environment variable to enable HMAC signature verification:

```bash
# .env
WEBHOOK_SECRET=your-random-secret-key-here
WEBHOOK_TIMEOUT=10  # Request timeout in seconds (default: 10)
WEBHOOK_MAX_RETRIES=3  # Max retry attempts (default: 3)
```

### Usage

#### Single Request with Webhook

```bash
curl -X POST "https://your-api.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -d '{
    "video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language": "en",
    "webhook_url": "https://your-app.com/webhook/subtitle"
  }'
```

#### Batch Request with Webhook

```bash
curl -X POST "https://your-api.com/api/v1/subtitles/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "video_ids": ["dQw4w9WgXcQ", "anotherVideoId"],
    "language": "en",
    "webhook_url": "https://your-app.com/webhook/subtitle"
  }'
```

### Webhook Payload

When a job completes (success or failure), the API sends a POST request with the following payload:

```json
{
  "event": "job.completed",
  "job_id": "abc123-def456-ghi789",
  "video_id": "dQw4w9WgXcQ",
  "status": "success",
  "result": {
    "success": true,
    "video_id": "dQw4w9WgXcQ",
    "title": "Video Title",
    "language": "en",
    "extraction_method": "youtube-transcript-api",
    "subtitle_count": 150,
    "duration_ms": 1234,
    "subtitles": [...],
    "plain_text": "Full transcript text..."
  },
  "timestamp": "2025-12-31T00:00:00Z"
}
```

For failed jobs:

```json
{
  "event": "job.completed",
  "job_id": "abc123-def456-ghi789",
  "video_id": "dQw4w9WgXcQ",
  "status": "failed",
  "error": "Video unavailable or subtitles disabled",
  "timestamp": "2025-12-31T00:00:00Z"
}
```

### Signature Verification

To verify webhook authenticity, the API includes an HMAC signature in the `X-Webhook-Signature` header:

```
X-Webhook-Signature: sha256=abc123def456...
X-Webhook-Timestamp: 2025-12-31T00:00:00Z
```

#### Verification Example (Python)

```python
import hmac
import hashlib
import json

def verify_webhook(payload: bytes, signature: str, timestamp: str, secret: str) -> bool:
    """Verify webhook signature."""
    # Create the message to verify
    message = f"{payload.decode()}.{timestamp}"

    # Generate expected signature
    expected = hmac.new(
        secret.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    # Compare with received signature
    received = signature.replace("sha256=", "")
    return hmac.compare_digest(expected, received)

# Usage
from fastapi import Request, HTTPException

@app.post("/webhook/subtitle")
async def handle_webhook(request: Request):
    payload = await request.body()
    signature = request.headers.get("X-Webhook-Signature", "")
    timestamp = request.headers.get("X-Webhook-Timestamp", "")

    if not verify_webhook(payload, signature, timestamp, YOUR_WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    # Process webhook...
    return {"status": "received"}
```

#### Verification Example (JavaScript/Node.js)

```javascript
const crypto = require("crypto");

function verifyWebhook(payload, signature, timestamp, secret) {
  const message = `${payload}.${timestamp}`;
  const expected = crypto
    .createHmac("sha256", secret)
    .update(message)
    .digest("hex");

  const received = signature.replace("sha256=", "");
  return crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(received));
}

// Express example
app.post("/webhook/subtitle", (req, res) => {
  const payload = JSON.stringify(req.body);
  const signature = req.get("X-Webhook-Signature");
  const timestamp = req.get("X-Webhook-Timestamp");

  if (!verifyWebhook(payload, signature, timestamp, YOUR_WEBHOOK_SECRET)) {
    return res.status(401).send("Invalid signature");
  }

  // Process webhook...
  res.send({ status: "received" });
});
```

### Retry Behavior

Webhooks are retried with exponential backoff:

| Attempt | Backoff   |
| ------- | --------- |
| 1       | Immediate |
| 2       | 1 second  |
| 3       | 2 seconds |

If all retries fail, the error is logged and the `webhook_delivery_status` in the database is set to `failed`.

### Best Practices

1. **Return 2xx status**: Your webhook endpoint should return a 2xx status code to indicate successful delivery. Any other status will trigger a retry.

2. **Process quickly**: Webhook delivery has a 10-second timeout. If your processing takes longer, acknowledge immediately and process asynchronously.

3. **Use HTTPS**: Always use HTTPS URLs for webhooks to ensure payload security.

4. **Verify signatures**: Always verify the HMAC signature to prevent webhook spoofing.

5. **Idempotency**: Design your webhook handler to be idempotent, as retries may deliver the same event multiple times.

6. **Logging**: Log all webhook deliveries for debugging and audit purposes.

## Deployment Information

### Prerequisites

- VPS: 107.174.42.198 (already set up)
- Docker & Docker Compose installed
- Redis running on `redis_default` network
- PostgreSQL running on `supabase_default` network
- Nginx-proxy running on `nginx-proxy_default` network

### Environment Variables Required

```
# Database
DB_PASSWORD=<supabase-password>
DATABASE_URL=postgresql+asyncpg://postgres:${DB_PASSWORD}@supabase-db:5432/postgres

# Security
JWT_SECRET=<secure-random-string>

# Optional
YT_PROXY_URLS=<comma-separated-proxy-urls>
SENTRY_DSN=<error-tracking-url>
```

### Resource Allocation

```
Per Instance (on shared VPS):
├── CPU: 0.5-1.5 vCPU
├── Memory: 256-512 MB
├── Network: 10 Mbps (YouTube limit is 256 kbps/s anyway)
└── Disk: 1 GB per instance (logs + temp)

Recommended:
├── API Servers: 2 instances
├── Workers: 2-4 instances (scale as needed)
└── Total: ~$20/month on shared VPS
```

## Deployment Checklist

### Pre-Deployment

- [ ] Read ARCHITECTURE.md for design decisions
- [ ] Review DEPLOYMENT.md for detailed steps
- [ ] Prepare .env.production with credentials
- [ ] Validate docker-compose.yml
- [ ] Test Redis and PostgreSQL connectivity

### Deployment

- [ ] Run `make build`
- [ ] Run `make deploy`
- [ ] Run `make health` (verify healthy status)
- [ ] Check logs: `make logs`
- [ ] Test API endpoints

### Post-Deployment

- [ ] Monitor logs for errors: `docker-compose logs -f`
- [ ] Check metrics: `curl http://localhost:8010/metrics`
- [ ] Set up monitoring dashboards (optional)
- [ ] Configure alerting rules (optional)
- [ ] Document any customizations

## Useful Commands

```bash
# Operational
make build              # Build Docker images
make deploy             # Deploy containers
make logs               # Stream logs
make health             # Health check all services
make down               # Stop containers
make clean              # Remove containers and images
make ps                 # Show running containers
make stats              # Show resource usage

# Scaling
make scale WORKERS=4    # Scale to 4 worker instances

# Database
make migrate-up         # Run migrations
make admin-clear-cache  # Clear all cache

# Development
make test               # Run unit tests
make lint               # Run linter
make format             # Format code
```

## Monitoring & Observability

### Key Metrics to Track

- **Extraction Success Rate** (target: >99.5%)
- **Extraction Latency** (P50: 2s, P95: 5s, P99: 30s)
- **Cache Hit Rate** (target: >70%)
- **Queue Depth** (alert if >50 jobs)
- **Error Rate** (alert if >5% for 5min)

### Structured Logging

All logs are output as JSON for easy aggregation:

```json
{
  "timestamp": "2025-12-30T18:45:00.123Z",
  "level": "INFO",
  "logger": "subtitle_extractor",
  "message": "extraction_completed",
  "video_id": "dQw4w9WgXcQ",
  "duration_ms": 1234,
  "cache_tier": "miss",
  "status": "success"
}
```

### Health Checks

```bash
# Kubernetes-style health check
curl http://localhost:8010/health

# Load balancer compatible (returns 200 or 503)
curl -f http://localhost:8010/health || exit 1

# Detailed status
curl http://localhost:8010/api/admin/queue/stats
```

## Response Headers

### Standard Headers

All API responses include the following headers:

| Header        | Type   | Description                                        |
| ------------- | ------ | -------------------------------------------------- |
| Content-Type  | string | Response content type (usually `application/json`) |
| X-Request-ID  | string | Unique identifier for this request (for tracing)   |
| X-API-Version | string | API version handling the request                   |

### Rate Limit Headers

All API responses (except health endpoints) include rate limit information:

| Header                | Type      | Description                                       |
| --------------------- | --------- | ------------------------------------------------- |
| X-RateLimit-Limit     | number    | Base requests per minute (e.g., `30`)             |
| X-RateLimit-Remaining | number    | Remaining requests in current window              |
| X-RateLimit-Reset     | timestamp | Unix timestamp when limit resets                  |
| X-RateLimit-Policy    | string    | Policy format: `{limit};w={window};burst={burst}` |
| Retry-After           | number    | Seconds to wait before retrying (only on 429)     |

**Example:**

```
HTTP/1.1 200 OK
Content-Type: application/json
X-Request-ID: abc123def456
X-API-Version: v1
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 25
X-RateLimit-Reset: 1735629600
X-RateLimit-Policy: 30;w=60;burst=5
```

### Error Headers

Error responses include additional headers:

| Header       | Type   | Description                           |
| ------------ | ------ | ------------------------------------- |
| Content-Type | string | `application/problem+json` for errors |
| X-Error-Code | string | Machine-readable error code           |

---

## Authentication

### API Key Authentication

Include your API key in the request header:

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key_here" \
  -d '{"video_id": "dQw4w9WgXcQ"}'
```

**Header Name:** `X-API-Key`

### JWT Bearer Token (Alternative)

Some deployments support JWT authentication:

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_jwt_token" \
  -d '{"video_id": "dQw4w9WgXcQ"}'
```

### Authentication Errors

**401 Unauthorized:** Missing or invalid credentials

```json
{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "Authentication required",
    "hint": "Provide a valid API key via X-API-Key header",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z"
  }
}
```

**403 Forbidden:** Valid credentials but insufficient permissions

```json
{
  "error": {
    "code": "FORBIDDEN",
    "message": "Access forbidden",
    "hint": "You do not have permission to access this resource",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z"
  }
}
```

---

## Request ID Tracing

### Overview

Every API request is assigned a unique `X-Request-ID` header that is returned in the response. This ID is used for tracing requests through the system and debugging issues.

### Custom Request IDs

You can provide your own request ID for distributed tracing:

```bash
curl -X POST "https://api.example.com/api/v1/subtitles" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: my-custom-request-123" \
  -d '{"video_id": "dQw4w9WgXcQ"}'
```

If not provided, a random UUID is generated.

### Using Request IDs for Debugging

When reporting issues, include the request ID:

1. **Extract from response:**

   ```bash
   curl -i "https://api.example.com/api/v1/subtitles/dQw4w9WgXcQ"
   # Look for: X-Request-ID: abc123def456
   ```

2. **Include in error reports:**

   ```
   Issue: Subtitle extraction failed
   Request ID: abc123def456
   Timestamp: 2025-12-31T00:00:00Z
   ```

3. **Server-side logging:**
   All logs include the request_id field for correlation:
   ```json
   {
     "request_id": "abc123def456",
     "level": "ERROR",
     "message": "extraction_failed",
     "video_id": "dQw4w9WgXcQ"
   }
   ```

### Distributed Tracing

For microservices architectures, propagate the request ID:

```python
import requests

def make_request(video_id):
    headers = {
        "Content-Type": "application/json",
        "X-Request-ID": generate_request_id()  # or pass-through from upstream
    }
    response = requests.post(
        "https://api.example.com/api/v1/subtitles",
        json={"video_id": video_id},
        headers=headers
    )
    return response
```

---

## Rate Limiting

**Strategy:** Token bucket algorithm in Redis

**Configuration:**

- 30 requests per minute per IP (configurable via RATE_LIMIT_REQUESTS_PER_MINUTE)
- Burst allowance: 5 requests (configurable via RATE_LIMIT_BURST_SIZE)
- Why 30? YouTube tolerates ~30-50 req/min before blocking

**Response on Rate Limit:**

```
HTTP 429 Too Many Requests
Retry-After: 45 (seconds until reset)
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1735629600

{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "hint": "Wait before making another request or upgrade your API plan",
    "request_id": "abc123",
    "timestamp": "2025-12-31T00:00:00Z",
    "meta": {
      "retry_after": 45,
      "reset_at": "2025-12-31T00:01:00Z"
    }
  }
}
```

**See [RATE_LIMITING.md](RATE_LIMITING.md) for detailed handling strategies.**

## Security Considerations

### yt-dlp Safety

- Runs only in Docker container (isolated)
- No write access to application code (read-only mount)
- Process kills on timeout (30 second hard limit)
- Version pinning (no auto-update)
- Monthly security reviews recommended

### Data Security

- No API token logging
- IP addresses hashed in logs
- JWT token validation
- CORS enabled for specified origins
- Environment variables for secrets

### Network Isolation

- Uses Docker networks (nginx-proxy_default, supabase_default, redis_default)
- No direct internet access except YouTube
- Optional proxy support for IP rotation

## Scaling Strategies

### Immediate (Current VPS)

```
2 FastAPI instances + 2-4 workers
Throughput: ~60 videos/minute
Cost: ~$20/month
```

### Near-term (Multi-VPS)

```
3 VPS with shared Redis/PostgreSQL
Throughput: ~200 videos/minute
Cost: ~$100/month
```

### Enterprise (Kubernetes)

```
Auto-scaling worker pool (0-50 replicas)
Cloud CDN for subtitle delivery
Managed database (Google Cloud SQL)
Throughput: 10,000+ videos/minute
Cost: $200-500/month
```

## Troubleshooting

### Service won't start

```bash
# Check logs
docker-compose logs api

# Validate configuration
docker-compose config

# Check network connectivity
docker network ls | grep default
```

### High memory usage

```bash
# Check per-process memory
docker stats --no-stream heavy-youtube-subtitles-api

# Reduce worker count or increase VPS RAM
```

### Queue backing up

```bash
# Check queue depth
redis-cli -n 2 LLEN youtube-extraction

# Add more workers
make scale WORKERS=8

# Monitor extraction time
docker-compose logs worker | grep duration_ms
```

### YouTube API blocking

```bash
# Check error rate
curl http://localhost:8010/metrics | grep extraction_error

# Enable proxy (if configured)
# YT_PROXY_URLS=https://proxy1.example.com:8080

# Reduce worker concurrency (slower but works)
# WORKER_CONCURRENCY=1
```

## Next Steps

1. **Week 1:** Follow DEPLOYMENT.md for production deployment
2. **Week 2:** Implement worker task execution (core feature)
3. **Week 3:** Set up monitoring dashboards and alerts
4. **Week 4:** Load test and performance tuning
5. **Week 5+:** Iterate on features based on usage patterns

## FAQ

**Q: Why async architecture instead of simple blocking API?**
A: YouTube extraction takes 5-30 seconds. Blocking would cause request queuing and poor user experience. Async allows parallel processing with independent scaling.

**Q: What happens if YouTube blocks our IP?**
A: Fallback to yt-dlp with user-agent rotation. Optional proxy support. Circuit breaker alerts on repeated failures.

**Q: How long are subtitles cached?**
A: 24 hours in Redis (hot), 30 days in PostgreSQL (cold). Configurable via environment variables.

**Q: Can we deploy workers on different machines?**
A: Yes. Shared Redis + PostgreSQL makes workers stateless. Deploy on any machine with network access.

**Q: What's the maximum throughput?**
A: Limited by YouTube rate limit (~30 req/min from single IP). With proxies or multiple extraction APIs: 200+ videos/minute.

## Support & Documentation

### For API Consumers

| Document              | Purpose                           | Link                                         |
| --------------------- | --------------------------------- | -------------------------------------------- |
| **User Guide**        | 5-minute getting started          | [USER_GUIDE.md](USER_GUIDE.md)               |
| **Integration Guide** | Python, JavaScript, cURL examples | [INTEGRATION_GUIDE.md](INTEGRATION_GUIDE.md) |
| **Error Codes**       | Error reference & troubleshooting | [ERROR_CODES.md](ERROR_CODES.md)             |
| **Rate Limiting**     | Rate limits & handling strategies | [RATE_LIMITING.md](RATE_LIMITING.md)         |

### For Deployers

| Document               | Purpose                              | Link                                                   |
| ---------------------- | ------------------------------------ | ------------------------------------------------------ |
| **Quick Start**        | 5-minute setup guide                 | [QUICK_START.md](QUICK_START.md)                       |
| **Architecture**       | Complete technical specification     | [ARCHITECTURE-REFERENCE.md](ARCHITECTURE-REFERENCE.md) |
| **Deployment**         | Step-by-step deployment instructions | [DEPLOYMENT.md](DEPLOYMENT.md)                         |
| **Deployment Summary** | Executive overview with diagrams     | [DEPLOYMENT_SUMMARY.md](DEPLOYMENT_SUMMARY.md)         |

### Interactive Documentation

- **OpenAPI Schema:** `/openapi.json`
- **Swagger UI:** `/docs` (when running locally)
- **ReDoc:** `/redoc` (when available)

## License

Internal use only.

---

**Last Updated:** 2025-12-31
**Maintainer:** Infrastructure Team
**Status:** Production Ready
**API Version:** v1

Ready to deploy? Start with: `./init.sh` then `make deploy`
