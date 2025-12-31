# YouTube Subtitle API - Deployment Summary

**Senior Principal Engineer Analysis** | Google/GCP Perspective | Large-Scale Infrastructure

## Quick Reference

| Aspect            | Decision                                      | Rationale                                                      |
| ----------------- | --------------------------------------------- | -------------------------------------------------------------- |
| **Placement**     | Heavy-Tasks (batch)                           | I/O-bound extraction workload, isolated from critical services |
| **Base Image**    | python:3.13-slim-bookworm                     | 150MB, security updates, optimal Python performance            |
| **Architecture**  | Async API + Worker Queue                      | Non-blocking request handling, independent extraction scaling  |
| **Cache Layer**   | Redis (distributed) + PostgreSQL (persistent) | 3-tier caching for <100ms repeated requests                    |
| **Rate Limiting** | 30 req/min per IP (token bucket)              | Prevents YouTube API blocking, fair resource allocation        |
| **Scaling**       | Horizontal (add workers)                      | Each worker can be scaled independently, stateless             |
| **Cost**          | ~$20/month (on shared VPS)                    | Efficient resource usage, no unnecessary overhead              |

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                      CLIENT REQUESTS (Internet)                     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────▼──────────────────┐
              │   Nginx Reverse Proxy             │
              │   (nginx-proxy_default)           │
              │   - SSL/TLS termination           │
              │   - Rate limit (nginx level)      │
              │   - Request routing               │
              └────────────────┬──────────────────┘
                               │
          ┌────────────────────▼──────────────────────┐
          │     FastAPI Service (Port 8010)           │
          │     heavy-youtube-subtitles-api:1.0       │
          │                                           │
          │  Handlers:                                │
          │  ├─ POST /api/subtitles                  │
          │  ├─ GET  /api/subtitles/{video_id}       │
          │  ├─ GET  /health                         │
          │  ├─ GET  /metrics                        │
          │  └─ POST /api/admin/*                    │
          │                                           │
          │  Middleware:                             │
          │  ├─ Rate limiting (30 req/min)           │
          │  ├─ Request logging (structured JSON)    │
          │  ├─ Error handling & circuit breaker    │
          │  └─ Prometheus metrics collection        │
          └────┬───────────┬───────────┬─────────────┘
               │           │           │
       ┌───────▼───┐  ┌────▼────┐  ┌──▼──────┐
       │   Tier 1  │  │  Tier 2  │  │  Tier 3  │
       │  In-Memory│  │  Redis   │  │PostgreSQL│
       │  Cache    │  │  Cache   │  │  Persist │
       │(5 min TTL)│  │(24h TTL) │  │(30d TTL) │
       └─────┬─────┘  └────┬─────┘  └──┬───────┘
             │             │            │
             └─────────────┼────────────┘
                           │
        ┌──────────────────▼──────────────────┐
        │    Redis Job Queue (redis:6379/2)   │
        │    - Persistent job tracking        │
        │    - Dead letter queue for errors   │
        │    - Result storage (24h)           │
        └──────────────────┬──────────────────┘
                           │
        ┌──────────────────▼──────────────────────────────────┐
        │                 Worker Pool                         │
        │  (Horizontally scalable, 2-N instances)            │
        │                                                      │
        │  ┌────────────────┐  ┌────────────────┐            │
        │  │ Worker-1       │  │ Worker-2       │  ... Worker-N
        │  │                │  │                │            │
        │  │ Processes:     │  │ Processes:     │            │
        │  │ ├─ Extract via │  │ ├─ Extract via │            │
        │  │ │ youtube-     │  │ │ youtube-     │            │
        │  │ │ transcript   │  │ │ transcript   │            │
        │  │ └─ Fallback:   │  │ └─ Fallback:   │            │
        │  │   yt-dlp       │  │   yt-dlp       │            │
        │  │                │  │                │            │
        │  │ Concurrency: 2 │  │ Concurrency: 2 │            │
        │  │ Memory: 256MB  │  │ Memory: 256MB  │            │
        │  │ CPU: 0.5-1.0   │  │ CPU: 0.5-1.0   │            │
        │  └────┬───────────┘  └────┬───────────┘            │
        │       │                   │                        │
        └───────┼───────────────────┼────────────────────────┘
                │                   │
        ┌───────▼───────────────────▼──────────┐
        │   Subtitle Database                   │
        │   (PostgreSQL @ supabase-db:5432)     │
        │                                       │
        │   Schema: youtube_subtitles           │
        │   Tables:                             │
        │   ├─ subtitle_records (results)       │
        │   └─ extraction_jobs (job tracking)   │
        │                                       │
        │   Features:                           │
        │   ├─ Automatic schema creation        │
        │   ├─ TTL-based cleanup (30 days)      │
        │   ├─ Job deduplication                │
        │   └─ Retry tracking                   │
        └───────────────────────────────────────┘


EXTERNAL DEPENDENCIES (YouTube):
┌─────────────────────────────────────────────────────────────┐
│                                                               │
│ ┌──────────────────┐  ┌──────────────────┐                  │
│ │ youtube-         │  │ yt-dlp           │                  │
│ │ transcript-api   │  │ (Fallback)       │                  │
│ │                  │  │                  │                  │
│ │ - Fast (cached)  │  │ - Headless       │                  │
│ │ - Requires no    │  │   browser        │                  │
│ │   auth           │  │ - Rate-limited   │                  │
│ │ - RPS limit: ~30 │  │ - Proxy support  │                  │
│ │ - 403/429 on     │  │ - Retry capable  │                  │
│ │   blocking       │  │                  │                  │
│ └────────┬─────────┘  └────────┬─────────┘                  │
│          │                     │                            │
│          └──────────┬──────────┘                            │
│                     │                                       │
│          ┌──────────▼────────────┐                         │
│          │   YouTube API/Videos  │                         │
│          │   (Public endpoints)  │                         │
│          └───────────────────────┘                         │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Deployment Stack Files

### Core Configuration

- **Dockerfile** - Multi-stage build (builder + runtime)
- **Dockerfile.worker** - RQ worker container
- **docker-compose.yml** - Service orchestration
- **requirements.txt** - Python dependencies (pinned versions)
- **Makefile** - Operational commands
- **.env.production** - Environment variables (secrets)

### Application Code

- **main.py** - FastAPI application entry point
- **src/core/config.py** - Pydantic settings management
- **src/core/logging_config.py** - Structured JSON logging
- **src/services/cache.py** - Redis cache management
- **src/services/database.py** - PostgreSQL async driver
- **src/services/rate_limiter.py** - Token bucket rate limiting
- **src/api/routes/health.py** - Health check endpoints
- **src/api/routes/subtitles.py** - Subtitle extraction endpoints
- **src/api/routes/admin.py** - Admin/monitoring endpoints
- **src/models/subtitle.py** - SQLAlchemy ORM models

### Documentation

- **ARCHITECTURE.md** - Comprehensive design document (this file)
- **DEPLOYMENT.md** - Step-by-step deployment instructions
- **DEPLOYMENT_SUMMARY.md** - Executive summary (this file)

---

## Implementation Checklist

### Phase 1: Foundation (Immediate)

- [x] Architecture decision framework
- [x] Container setup (Dockerfile, docker-compose)
- [x] FastAPI skeleton with core routes
- [x] Cache layer (Redis integration)
- [x] Rate limiting (token bucket)
- [x] Structured logging (JSON format)
- [ ] Database models (SQLAlchemy)
- [ ] Health check endpoints

### Phase 2: Core Extraction (Week 1-2)

- [ ] youtube-transcript-api integration
- [ ] yt-dlp fallback mechanism
- [ ] Retry logic with exponential backoff
- [ ] Error handling & circuit breaker
- [ ] Timeout management (30s per extraction)

### Phase 3: Async Processing (Week 2-3)

- [ ] RQ job queue setup
- [ ] Worker process implementation
- [ ] Job status tracking
- [ ] Async callback handling
- [ ] Dead letter queue for failed jobs

### Phase 4: Observability (Week 3)

- [ ] Prometheus metrics integration
- [ ] Grafana dashboard
- [ ] Alert rules (cpu, memory, errors)
- [ ] Log aggregation setup
- [ ] Distributed tracing (optional)

### Phase 5: Performance (Week 4)

- [ ] Load testing (k6/locust)
- [ ] Database query optimization
- [ ] Connection pool tuning
- [ ] Cache warming strategy
- [ ] Worker auto-scaling logic

---

## Key Technical Decisions Explained

### 1. Heavy-Tasks vs Standalone-Apps

**Why Heavy-Tasks?**

The YouTube subtitle extraction is fundamentally different from real-time services:

```
Extraction Characteristics:
├─ Duration: 5-30 seconds per video (I/O-bound network latency)
├─ Dependencies: External YouTube API (can fail/block)
├─ Resource Usage: CPU minimal (<5%), network significant
├─ Concurrency: Limited by YouTube rate limits (~30/min from one IP)
├─ Scaling: Horizontal (more workers = more throughput)
└─ Failure Mode: Graceful (cache misses trigger re-extraction)

Standalone-Apps Workload:
├─ Duration: Sub-second responses (real-time)
├─ Dependencies: Internal (predictable SLO)
├─ Resource Usage: CPU + Memory significant
├─ Concurrency: High (100+ concurrent connections)
├─ Scaling: Vertical-first (more powerful VM)
└─ Failure Mode: Catastrophic (affects user experience immediately)
```

**Impact:**

- Isolates extraction failures from critical services
- Allows independent scaling (add 5 workers without affecting other services)
- Prevents thundering herd on YouTube API
- Enables graceful degradation (cached results still serve)

### 2. Python 3.13-slim-bookworm Base Image

**Size Comparison:**

```
python:3.13-alpine          80 MB  (missing glibc, yt-dlp compile issues)
python:3.13-slim-bookworm  150 MB  (chosen: balanced)
python:3.11-slim-bookworm  145 MB  (2% slower)
python:3.13-full           900 MB  (6x bloat, unnecessary)
```

**Why Bookworm?**

- Current Debian stable (security updates until 2027)
- Full glibc support (yt-dlp binary dependencies work)
- Smaller than Alpine but more compatible than full image

**Performance Gain (3.13 vs 3.11):**

- 10-15% faster bytecode execution
- Improved asyncio performance (critical for our use case)
- Better memory management for long-running processes

### 3. Async Architecture (FastAPI + RQ + Workers)

**Alternative: Synchronous Service**

```python
# Single-threaded, blocks on YouTube
@app.post("/extract")
def extract_subtitles(video_id):
    result = youtube_api.get_subtitles(video_id)  # Blocks 5-30s
    return result
```

**Problem:** All other requests wait behind extraction (convoy effect)

**Our Approach: Async Job Queue**

```
Request  → API (responds in <10ms) → Queue in Redis
         ↑
         └─ Worker (extracts in parallel, saves to DB)
                    ↓
         Client polls /api/job/{job_id} for status
         ↓
         Results ready in DB, cached for reuse
```

**Benefits:**

- API responds immediately (queue receipt, not result)
- Multiple parallel workers (scale independently)
- Results persisted (avoids re-extraction)
- Clients can check status async

### 4. 3-Tier Caching Strategy

```
First Request (Cache Miss):
API → Tier 1 (miss) → Tier 2 (miss) → Tier 3 (miss)
                                   → Worker extracts (5-30s)
                                   → Tier 3 stores (PostgreSQL)
                                   → Tier 2 populates (Redis, 24h)
                                   → Tier 1 populates (in-memory, 5min)
                  ↓
            Response (30s latency)

Second Request (Cache Hit, within 5 min):
API → Tier 1 (hit) → Response (<1ms)

N-th Request (Cache Hit, within 24h):
API → Tier 1 (miss) → Tier 2 (hit) → Response (<10ms)

After 24h (Cache Expired):
API → Tier 1 (miss) → Tier 2 (miss) → Tier 3 (hit) → Repopulate Tier 2
                  → Response (~50ms, DB latency)
```

**Cost Analysis:**

- 100 videos/day = 10% hit from Tier 1, 60% from Tier 2, 30% from Tier 3
- No re-extraction for popular videos (massive savings)
- Tier 1 (in-memory) prevents Redis round-trips for hottest data

### 5. Rate Limiting: 30 req/min per IP

**Why 30?**

- YouTube tolerates ~30-50 requests/min from single IP
- Beyond that: 403 (Forbidden) or 429 (Too Many Requests)
- Our limit: 30 to stay below threshold
- Burst allowance: 5 (helps autocomplete use cases)

**Implementation: Token Bucket**

```python
# Per IP, per endpoint
Token count: starts at 30
Refill rate: 2 tokens/second (30 per 60s)
Burst: 5 extra tokens allowed

# First 5 requests: instant
# Requests 6-30: served at 2/sec rate
# Request 31+: rejected with 429 until refill
```

**Redis Key:** `ratelimit:{client_ip}:{endpoint_hash}`

- TTL: 61 seconds (respects minute boundary)
- Distributed (works across multiple servers)
- Atomic operations (no race conditions)

---

## Production Considerations

### Security Hardening

**yt-dlp Risk Mitigation:**

```dockerfile
# Run only in Docker container with:
├─ No write access to /app (read-only mount)
├─ No sudo/elevation
├─ Process kill on timeout (30s hard limit)
├─ Network whitelist (YouTube + proxy IPs only)

# Disable dangerous features:
├─ postprocessor plugins
├─ arbitrary --exec commands
├─ FFmpeg integration (if not needed)
└─ External config loading

# Version pinning:
├─ Explicit pip freeze (no auto-update)
├─ Monthly security audits
└─ Changelog review before upgrade
```

**Data Security:**

- No logging of API tokens/JWT
- No logging of user IP addresses (hash instead)
- Sensitive errors never exposed to client
- Request signing (optional JWT validation)

### Observability (Critical for 24/7 Operation)

**Metrics to Track:**

```
1. Extraction Success Rate
   - Target: >99.5%
   - Alert: <99% for 5min

2. Extraction Latency
   - P50: 2s (primary API)
   - P95: 5s (timeout safe)
   - P99: 30s (hard limit)

3. Cache Hit Rate
   - Target: >70%
   - Alert: <50% (cache busted or TTL too short)

4. Queue Depth
   - Target: <10 jobs
   - Alert: >50 (worker shortage)

5. Error Distribution
   - youtube-transcript-api failures
   - yt-dlp failures (fallback used)
   - Network timeouts
   - Rate limit hits
```

### Cost Optimization

**Current VPS (Shared):**

- Compute: $10/month (1/4 shared VPS)
- Bandwidth: $7.50/month (50GB YouTube inbound)
- Database: $1.33/month (1/6 shared Supabase)
- **Total: ~$20/month**

**If Traffic Grows (>1000 videos/day):**

1. Add 2nd VPS for workers ($40/month)
2. Scale to 3-4 worker VPS ($100-150/month)
3. Consider Kubernetes on GKE ($200-300/month base)

**Cost Avoidance:**

- No FFmpeg (saves 200MB image, reduces complexity)
- No browser automation (selenium/playwright would double resource usage)
- Efficient caching (avoids re-extraction costs)

---

## Monitoring & Alerting Setup (Recommended)

```yaml
# Prometheus Rules
groups:
  - name: youtube_api
    rules:
      - alert: ExtractorHighErrorRate
        expr: rate(extraction_errors[5m]) > 0.05
        for: 5m
        annotations:
          summary: "Extraction error rate > 5%"

      - alert: QueueDepthHigh
        expr: job_queue_depth > 50
        for: 5m
        annotations:
          summary: "{{ $value }} jobs waiting, add workers"

      - alert: CacheHitRateLow
        expr: cache_hit_rate < 0.5
        for: 1h
        annotations:
          summary: "Cache hit rate < 50%, investigate TTL"

      - alert: ApiLatencyHigh
        expr: histogram_quantile(0.99, extraction_duration) > 30s
        for: 5m
        annotations:
          summary: "P99 latency > 30s, check YouTube API"
```

---

## Migration Path (If Needed)

### Phase 1: Current (Single VPS)

- 2 FastAPI instances
- 2-4 worker processes
- Throughput: ~60 videos/min

### Phase 2: Multi-VPS (2-3 machines)

- Shared Redis (cluster mode)
- Shared PostgreSQL (with read replicas)
- Throughput: ~200 videos/min

### Phase 3: Kubernetes (Enterprise)

- Auto-scaling worker pool (0-50 replicas)
- Cloud CDN for subtitle delivery
- Managed database (Google Cloud SQL)
- Throughput: 10,000+ videos/min

---

## Files to Review

Before deployment, ensure these are finalized:

1. **ARCHITECTURE.md** (34KB) - Complete technical specification
2. **DEPLOYMENT.md** (15KB) - Step-by-step deployment guide
3. **Dockerfile** (1.2KB) - Multi-stage build
4. **docker-compose.yml** (5KB) - Service orchestration
5. **main.py** (8KB) - FastAPI application
6. **requirements.txt** (2KB) - Pinned dependencies

---

## Questions & Answers

**Q: Why not use Kubernetes now?**
A: VPS cost-effective for current scale (<100 videos/day). Kubernetes adds $200/month overhead. Migrate when approaching worker bottleneck (threshold: 500+ videos/day).

**Q: What if YouTube blocks our IP?**
A: Fallback to yt-dlp with user-agent rotation. Optional proxy support via YT_PROXY_URLS env var. Circuit breaker triggers alert after 3 consecutive failures.

**Q: How long are subtitles cached?**
A: 24 hours in Redis (hot cache), 30 days in PostgreSQL (cold cache). Configurable via REDIS_RESULT_TTL and db retention policy.

**Q: Can workers be on different machines?**
A: Yes. Shared Redis + PostgreSQL makes workers stateless. Deploy worker containers on any VPS with network access to Redis/DB.

**Q: What's the maximum throughput?**
A: Current VPS: 60 videos/min (limited by YouTube rate limit of 30 req/min). With proxies or secondary extraction API: 200+ videos/min.

---

## Next Steps

1. **Review ARCHITECTURE.md** - Full technical specification
2. **Execute DEPLOYMENT.md** - Step-by-step deployment
3. **Implement Worker Tasks** - Week 1-2 (core feature)
4. **Set Up Monitoring** - Week 3 (observability)
5. **Load Test** - Week 4 (performance validation)

---

**Document Version:** 1.0
**Generated:** 2025-12-30
**Status:** Ready for Implementation
**Confidence Level:** High (follows GCP best practices for async batch processing)
