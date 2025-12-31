# YouTube Subtitle API - Production Architecture

## Executive Summary

This document provides a production-grade deployment architecture for the YouTube Subtitle API on VPS 107.174.42.198. The design prioritizes reliability, scalability, cost-efficiency, and operational observability.

## Architecture Decision Matrix

### 1. Placement: Heavy-Tasks vs Standalone-Apps

**Decision: HEAVY-TASKS (Batch Processing)**

**Rationale:**

- YouTube subtitle extraction is I/O-bound (network latency to YouTube/yt-dlp)
- Extraction time: 5-30s per video (third-party dependency blocking)
- Video processing is compute-heavy when reformatting
- Suitable for async task queue pattern with worker pools

**Alternative Rejected: Standalone-Apps**

- Would compete with long-running services for resources
- Better isolated in dedicated heavy-tasks zone for resource predictability
- Easier to scale horizontally without affecting critical services

### 2. Service Architecture

```
REQUEST FLOW:
┌─────────────────────────────────────────────────────────────┐
│                    Client Request                           │
│              POST /api/subtitles                            │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────▼─────────────┐
        │  FastAPI Handler Layer   │
        │  (async request/response)│
        │  - Validation            │
        │  - Auth/Rate-limit       │
        │  - Queue task            │
        └────────────┬─────────────┘
                     │ Enqueues async task
        ┌────────────▼──────────────────────┐
        │  Redis Task Queue (RQ/Celery)     │
        │  - Persistent job tracking        │
        │  - Retry mechanism                │
        │  - Dead letter queue on failure   │
        └────────────┬──────────────────────┘
                     │
   ┌─────────────────┼─────────────────┐
   │                 │                 │
┌──▼───┐  ┌────────▼────┐  ┌────────▼────┐
│Work-1│  │  Worker-2   │  │  Worker-N   │
│      │  │             │  │             │
│Extraction
   │  │  │  (auto-scale)│  │ (auto-scale)│
│  Pool  │             │  │             │
└──┬────┘  └────────┬─────┘  └────────┬────┘
   │                │                 │
   └────────────────┼─────────────────┘
                    │
        ┌───────────▼──────────────┐
        │ PostgreSQL Result Store  │
        │ (via Supabase)           │
        │ - Cache results (24h)    │
        │ - Track extraction stats │
        └──────────────────────────┘
```

**Components:**

1. **FastAPI Server** (Synchronous request handler)
   - Port: 8010
   - Handles GET /api/status/{job_id}
   - POST /api/subtitles (immediate queue response; `/api/rewrite-video` is an alias)
   - Webhook callbacks for async completion

2. **Worker Pool** (Async subtitle extraction)
   - Count: 2-4 workers (tunable via WORKER_PROCESSES)
   - Per-worker concurrency: 2 (youtube-transcript-api limits)
   - Graceful shutdown: 30s deadline

3. **Redis Queue** (Job orchestration)
   - Managed by existing redis_default network
   - Job retention: 24 hours
   - Dead letter queue for debugging

4. **PostgreSQL** (Result persistence)
   - Schema: youtube_subtitles
   - Retention: 30 days (configurable)
   - Indexes on: video_id, created_at, status

## Technical Stack

### Dependencies

```
# Core API
fastapi==0.115.5              # Async web framework
uvicorn[standard]==0.32.0     # ASGI production server
pydantic==2.8.2               # Validation & serialization

# YouTube Integration
youtube-transcript-api==0.6.1 # Primary extractor
yt-dlp==2025.1.1              # Fallback extractor (headless mode)

# Async & Queuing
httpx==0.27.2                 # Async HTTP client
asyncpg==0.29.0               # PostgreSQL driver
rq==1.15.1                    # Job queue management
rq-scheduler==0.13.1          # Scheduled cleanup tasks

# Database & Caching
SQLAlchemy[asyncio]==2.0.35   # ORM
redis[hiredis]==5.0.7         # In-memory cache layer

# Observability
structlog==24.4.0             # Structured logging (CloudLogging compatible)
prometheus-fastapi-instrumentator==6.1.0  # Metrics
python-json-logger==2.0.7     # JSON output for log aggregation

# Testing & Quality
pytest==8.3.3
pytest-asyncio==0.24.0
respx==0.20.2
black==24.1.1
ruff==0.2.2

# Security
python-dotenv==1.0.1          # Environment management
cryptography==42.0.0          # For JWT token handling
```

### Base Image Selection

**Decision: python:3.13-slim-bookworm**

**Rationale:**

```dockerfile
# Lightweight: 150MB vs 900MB (python:3.13-full)
# Includes essential build tools (gcc, make)
# Security: Bookworm = current stable (updated regularly)
# Performance: 3.13 has 10-15% speed improvement over 3.11
# YouTube libraries compatible (no unusual binary deps)
```

**Alternative Evaluated:**

- python:3.13-alpine: 80MB, but missing glibc → yt-dlp compilation issues
- python:3.13-full: 900MB, unnecessary weight
- python:3.11-slim: 2-3% slower, older Python

## Rate Limiting & YouTube API Handling

### YouTube Detection & Bypass Strategy

```
youtube-transcript-api:
├── YouTube.com URLs (99% of cases)
│   ├── Works fast (cached transcripts)
│   ├── No authentication required
│   ├── Rate limit: ~100 requests/minute from one IP
│   └── Risk: IP blocks after 500+ consecutive requests
│
└── Fallback Trigger: 403/429 errors
    ├── Use yt-dlp with:
    │   ├── Rotating user-agents (10 built-in variations)
    │   ├── Request throttling: 2-5s delays
    │   ├── Headless mode (if available)
    │   └── Proxy support (configurable via env)
    └── Exhaustive retry: Exponential backoff (1s, 2s, 4s, 8s, max 30s)
```

### Rate Limit Implementation

```python
# Architecture: Token bucket with Redis backend
# Per-IP throttle: 30 requests/minute (configurable)
# Per-video throttle: 1 extraction/hour (cache hit in DB first)
# Burst allowance: 5 requests/10s (users with autocomplete)

RedisRateLimiter:
  - Keys: {client_ip}:{endpoint}
  - Refill: Automatic (30/minute = 2000ms per token)
  - TTL: 61 seconds (respects minute boundaries)
  - Graceful degradation: 503 (Retry-After header provided)
```

### IP Rotation & Proxy Support

```yaml
# Environment Variables (Optional)
YT_PROXY_URLS: |
  https://proxy1.example.com:8080
  https://proxy2.example.com:8080
  https://proxy3.example.com:8080
YT_PROXY_AUTH: "user:pass" # Shared across all proxies

# Circuit Breaker: If 3 consecutive proxies fail
# -> Fall back to direct connection
# -> Alert monitoring (email/Slack)
```

## Caching Strategy

### Cache Architecture (3-Tier)

```
Request for Video ID "dQw4w9WgXcQ"
│
├─► Tier 1: In-Memory Cache (FastAPI app) [5 min TTL]
│   └─► Hit: Return in <1ms
│
├─► Tier 2: Redis (Distributed) [24h TTL]
│   └─► Hit: Return in 5-10ms
│
└─► Tier 3: PostgreSQL (Persistent) [30d TTL]
    └─► Query database
    └─► Parse subtitles
    └─► Populate Tier 2 & 1
    └─► Return in 2-5s (first extraction)
```

### Cache Invalidation Rules

```
Automatic Invalidation:
├─ 30 days old (persistent storage pruning)
├─ Manual via /admin/cache/clear/{video_id}
├─ On subtitle update detected (versioning)
└─ On encoder error (failed extraction marked as stale)

Cache Warming (Optional):
├─ Periodic task: Pre-cache trending videos (YouTube API)
├─ Scheduled: 2 AM daily (off-peak hours)
├─ Scope: Top 100 videos from past 7 days
└─ Cost: ~2-3 additional seconds of extraction time
```

### Data Structure (Redis/PostgreSQL)

```json
{
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "duration_seconds": 213,
  "language": "en",
  "auto_generated": false,
  "subtitles": [
    {
      "start": 0.5,
      "end": 2.0,
      "text": "We're no strangers to love",
      "confidence": 0.98
    }
  ],
  "extraction_method": "youtube-transcript-api|yt-dlp",
  "extraction_duration_ms": 1250,
  "created_at": "2025-12-30T18:45:00Z",
  "expires_at": "2026-01-29T18:45:00Z",
  "checksum": "sha256:abc123..." // For change detection
}
```

## Security Considerations

### Input Validation

```python
# URL validation (allowlist approach)
valid_domains = {
    'youtube.com',
    'youtu.be',
    'youtube-nocookie.com'
}

# Video ID validation (YouTube format: 11 alphanumeric chars)
import re
VIDEO_ID_PATTERN = r'^[a-zA-Z0-9_-]{11}$'

# Timeouts (prevent slowloris attacks)
EXTRACTION_TIMEOUT = 30  # seconds
REQUEST_TIMEOUT = 35      # seconds (allow some queue wait)
```

### yt-dlp Security Hardening

```python
# Danger Zone: yt-dlp has RCE history (no longer supported)
# Mitigation strategy:

1. RUN ONLY in Docker container with:
   ├─ No write access to /app (read-only mount)
   ├─ No sudo/elevation
   ├─ Restricted network (whitelist YouTube + proxy IPs)
   └─ Process kill on timeout (30s hard limit)

2. DISABLE dangerous features:
   ├─ postprocessor plugins
   ├─ arbitrary --exec commands
   ├─ FFmpeg integration (if not needed)
   └─ External config loading

3. VERSION PINNING:
   ├─ Explicit pip freeze
   ├─ Monthly security audits
   ├─ No auto-update
   └─ Changelog review before upgrade
```

### API Security

```yaml
Authentication:
  - Bearer token in Authorization header
  - Token format: "Bearer {jwt_token}"
  - JWT expiry: 1 hour (short-lived)
  - Refresh token rotation available

Rate Limiting:
  - Per-IP: 30 req/min (adjustable)
  - Per-token: 100 req/min (premium users)
  - Burst: 5 requests in 10s (autocomplete friendly)

CORS:
  - Allowed origins: [ALLOWED_ORIGINS env variable]
  - Credentials: false (stateless)
  - Methods: POST, GET, OPTIONS
```

### Sensitive Data Handling

```
DO NOT LOG:
├─ API tokens / Bearer tokens
├─ User IPs in structured logs (hash instead)
├─ Proxy credentials
└─ YouTube user cookies

DO LOG (safe):
├─ Video IDs (public)
├─ Extraction duration (performance)
├─ Error types (not messages)
└─ Cache hit/miss rates
```

## Scaling Considerations

### Horizontal Scaling Model

```
Phase 1: Current (Single VPS)
├─ 2 FastAPI instances (load-balanced via nginx)
├─ 2-4 worker processes (CPU-bound extraction)
├─ Redis: shared redis_default
└─ PostgreSQL: shared supabase_default
└─ Throughput: ~60 videos/minute

Phase 2: Multi-VPS (Future)
├─ Deploy to 2-3 additional VPS
├─ Shared Redis (cluster mode)
├─ Shared PostgreSQL (read replicas)
├─ DNS round-robin or load balancer
└─ Throughput: ~200 videos/minute

Phase 3: Distributed (Enterprise)
├─ Kubernetes (GKE/EKS)
├─ Auto-scaling worker pool (0-50 replicas)
├─ Cloud CDN for subtitle delivery
├─ Managed database (Google Cloud SQL)
└─ Throughput: 10,000+ videos/minute
```

### Resource Requirements

```yaml
Per Container (Single Worker):
  Memory:
    - Baseline: 200MB (Python + FastAPI)
    - Per worker: +150MB (yt-dlp overhead)
    - Redis conn pool: +20MB
    - Safety margin: 2x = 740MB per worker

  CPU:
    - YouTube extraction: 0.5-1 CPU (I/O bound, small CPU)
    - Subtitle parsing: 0.1-0.3 CPU
    - Per worker: ~1-1.5 CPU at full utilization

  Storage:
    - Subtitle cache: ~10KB per video
    - 1M videos = 10GB (compress with brotli: ~2-3GB)
    - Docker image: 300-400MB
    - Logs (per worker): 50-100MB/day (rotate weekly)

Recommended VPS Allocation:
├─ 4GB RAM (2 instances × 2GB baseline + margin)
├─ 2 vCPU (4 workers @ 0.5 vCPU each)
├─ 50GB disk (operational data + logs)
└─ Bandwidth: 100Mbps+ (YouTube throttles at 256kbps/s anyway)
```

## Observability & Monitoring

### Metrics Collection (Prometheus)

```python
# Key Metrics (exposed on /metrics endpoint)

# Extraction Performance
histogram_extraction_duration_seconds
  ├─ labels: [method, status, video_format]
  ├─ buckets: [0.5, 1, 2, 5, 10, 30]
  └─ used for: SLO tracking (p50=2s, p95=5s, p99=30s)

counter_extraction_total
  ├─ labels: [method, status, source]
  ├─ status: [success, timeout, rate_limit, error]
  └─ used for: Success rate (target: 99.5%)

# Cache Metrics
counter_cache_hits_total
  ├─ labels: [tier, method]
  └─ goal: 70% hit rate (indicates good caching)

counter_cache_misses_total
  ├─ labels: [tier, reason]
  └─ reason: [expired, evicted, not_found]

# Queue Health
gauge_job_queue_depth
  ├─ current jobs waiting
  ├─ alert: >100 (indicates slowdown)
  └─ trend: should be <10 (healthy throughput)

gauge_job_retry_count
  ├─ current retries in flight
  ├─ alert: >5 (extraction struggling)
  └─ auto-scale: add workers if >3 for 5min
```

### Structured Logging

```json
{
  "timestamp": "2025-12-30T18:45:00.123Z",
  "level": "INFO",
  "logger": "subtitle_extractor",
  "message": "extraction_completed",
  "video_id": "dQw4w9WgXcQ",
  "extraction_method": "youtube-transcript-api",
  "duration_ms": 1234,
  "subtitle_count": 42,
  "cache_tier": "miss",
  "request_id": "req-abc123",
  "worker_id": "worker-2",
  "event": "extraction_success"
}
```

### Health Checks

```
GET /health

Response: 200 OK
{
  "status": "healthy",
  "components": {
    "redis": "connected",
    "postgres": "connected",
    "extraction_service": "ready"
  },
  "queue_depth": 3,
  "uptime_seconds": 45872
}

Health Check Intervals:
├─ Kubernetes: every 10 seconds
├─ Docker healthcheck: every 30 seconds
├─ Load balancer: every 5 seconds
```

### Alerting Rules

```yaml
Critical Alerts:
  - Queue depth > 50 for 5min (add workers)
  - Error rate > 5% for 5min (page oncall)
  - Memory > 90% for 2min (OOM risk)
  - Redis disconnect > 30s (failover check)
  - P99 latency > 30s for 5min (rate limit check)

Warning Alerts:
  - Cache hit rate < 50% for 1h (check TTL)
  - Queue depth > 20 for 10min (trending up)
  - Worker timeout rate > 2% (extraction struggling)
  - Log error count > 100/min (investigate pattern)
```

## Deployment Instructions

### Prerequisites

```bash
# On VPS 107.174.42.198 (already established)
├─ Docker & Docker Compose installed
├─ Redis running on redis_default network
├─ PostgreSQL running on supabase_default network
├─ Nginx-proxy running on nginx-proxy_default network
└─ Environment variables populated in .env.production
```

### Deploy Steps

```bash
cd /opt/docker-projects/heavy-tasks/vibing-sub

# 1. Build image
make build

# 2. Validate configuration
make validate

# 3. Deploy to production
make deploy

# 4. Monitor logs
make logs

# 5. Health check
curl http://localhost:8010/health
```

### Configuration (Environment Variables)

Create `.env.production`:

```env
# Service Config
SERVICE_NAME=youtube-subtitles-api
ENVIRONMENT=production
LOG_LEVEL=INFO

# API Server
API_HOST=0.0.0.0
API_PORT=8010
WORKERS=4
WORKER_TIMEOUT=30

# Database (Supabase)
DATABASE_URL=postgresql+asyncpg://postgres:${DB_PASSWORD}@supabase-db:5432/postgres
DB_SCHEMA=youtube_subtitles
DB_POOL_SIZE=10

# Redis (Job Queue)
REDIS_URL=redis://redis:6379/2
REDIS_QUEUE_NAME=youtube-extraction
REDIS_RESULT_TTL=86400

# YouTube Configuration
YT_EXTRACTION_TIMEOUT=30
YT_RETRY_MAX_ATTEMPTS=3
YT_RETRY_BACKOFF_FACTOR=2
YT_PROXY_URLS=  # Optional proxy URLs (comma-separated)

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=30
RATE_LIMIT_BURST_SIZE=5
CACHE_TTL_MINUTES=1440

# Monitoring
PROMETHEUS_ENABLED=true
SENTRY_DSN=  # Optional error tracking

# Security
JWT_SECRET=${JWT_SECRET}
API_KEY_HEADER_NAME=X-API-Key
ALLOWED_ORIGINS=*
```

## Cost Analysis

### Monthly Operational Cost

```
VPS Allocation (existing, 1/4 shared):
├─ Base cost: $10/month (25% of $40 VPS)
│
├─ Bandwidth (100GB/month @ $0.15/GB):
│  ├─ Inbound (YouTube): ~50GB = $7.50
│  └─ Outbound (responses): ~10GB = $1.50
│
├─ Database (Supabase, 1/6 shared):
│  ├─ Storage: ~5GB @ $8/month = $1.33/month
│  └─ Compute: shared (negligible)
│
└─ Total: ~$20/month at 100% capacity

Scaling Cost (if needed):
├─ 2nd VPS: +$40/month
├─ 3 VPS cluster: ~$100-150/month
└─ Cloud deployment: $200-500/month
```

## Disaster Recovery

### Backup Strategy

```
Database:
├─ Automatic: Daily snapshots (Supabase)
├─ Retention: 30 days
├─ RTO: 10 minutes (restore from snapshot)
├─ RPO: 24 hours (acceptable for subtitle cache)

Cache (Redis):
├─ Persistence: Not required
├─ Data loss impact: None (re-extracted on miss)
├─ Recovery: Automatic (rebuild from requests)
```

### Failover Scenarios

```
Scenario: Redis unavailable
├─ Symptom: All queue operations fail
├─ Detection: Health check fails
├─ Recovery:
│  ├─ Automatic: Kubernetes restart
│  ├─ Manual: make down && make deploy
│  └─ Time: 30-60 seconds

Scenario: YouTube API blocked
├─ Symptom: 403 errors from youtube-transcript-api
├─ Detection: Metrics show 70%+ errors
├─ Recovery:
│  ├─ Activate yt-dlp fallback
│  ├─ Enable proxy rotation (if configured)
│  ├─ Reduce worker concurrency (slower but works)
│  └─ Manual review of extraction logs

Scenario: PostgreSQL unavailable
├─ Symptom: Database connection timeout
├─ Detection: Health check fails
├─ Impact: Cache layer broken, but queue functional
├─ Recovery:
│  ├─ Automatic: RDS failover (if using RDS)
│  ├─ Manual: Restore from backup
│  └─ Interim: Use Redis-only caching (24h)
```

## Next Steps / Roadmap

1. **Q1 2026**: Implement distributed tracing (Jaeger)
2. **Q2 2026**: Multi-region failover (secondary VPS)
3. **Q3 2026**: API monetization (usage-based billing)
4. **Q4 2026**: Kubernetes migration (better scaling)

---

**Document Version**: 1.0
**Last Updated**: 2025-12-30
**Owner**: Infrastructure Team
