# YouTube Subtitle API - GENESIS

> Implementation Plan v1.0 | 2025-12-30
> Multi-LLM Meeting Synthesis (Codex + Gemini + BigModel)

---

## Executive Summary

| Item             | Decision                                                 |
| ---------------- | -------------------------------------------------------- |
| **Project**      | YouTube Subtitle Extraction API                          |
| **Location**     | `/opt/docker-projects/heavy-tasks/youtube-subtitle-api/` |
| **Architecture** | Single container, dual-engine extraction                 |
| **Port**         | 8020 (internal)                                          |
| **Base Image**   | `python:3.10-slim-bookworm`                              |
| **Cost**         | ~$2-5/month (shared VPS resources)                       |

---

## 1. Architecture Decision

### 1.1 Placement: heavy-tasks (Confirmed)

```
/opt/docker-projects/
├── nginx-proxy/           # Gateway
├── supabase/              # Database
├── standalone-apps/       # Long-running services
└── heavy-tasks/           # <-- HERE
    └── youtube-subtitle-api/
```

**Rationale (3-model consensus):**

- I/O-bound workload (network latency to YouTube)
- Variable traffic pattern (burst → idle)
- No 24/7 uptime requirement
- Cost optimization (on-demand resources)

### 1.2 Dual-Engine Strategy (Direct First, Proxy on Failure)

```
Request → youtube-transcript-api (DIRECT, no proxy)
              ↓ success? → Return
              ↓ on 403/429/blocked
          youtube-transcript-api (with PROXY rotation)
              ↓ success? → Return
              ↓ still fails
          yt-dlp fallback (DIRECT, no proxy)
              ↓ success? → Return
              ↓ on 403/429/blocked
          yt-dlp (with PROXY rotation)
              ↓
          Clean for AI consumption
              ↓
          Return JSON + plain_text
```

| Engine                 | Speed | Reliability | Use Case         |
| ---------------------- | ----- | ----------- | ---------------- |
| youtube-transcript-api | ~3s   | 92%         | Primary (Direct) |
| yt-dlp                 | ~15s  | 99%         | Fallback         |
| Proxy Rotation         | +2s   | +5%         | On network error |

**Proxy Logic**: Server IP is used by default. Proxies are only used when direct connection fails with 403/429/blocked/timeout errors.

---

## 2. Technical Stack

### 2.1 Dependencies (Minimal)

```
fastapi==0.115.5
uvicorn[standard]==0.32.0
pydantic==2.8.2
youtube-transcript-api==0.6.1
yt-dlp==2024.12.6
structlog==24.4.0
cachetools==5.3.2
```

### 2.2 Container Specification

```yaml
Base Image: python:3.10-slim-bookworm
Memory: 512MB limit / 256MB reserved
CPU: 1 core limit
Port: 8020 → 8000
Health: /health endpoint
User: non-root (apiuser)
```

---

## 3. API Specification

### 3.1 Endpoints

| Method | Path             | Description       |
| ------ | ---------------- | ----------------- |
| GET    | `/health`        | Health check      |
| GET    | `/`              | API info          |
| POST   | `/api/subtitles` | Extract subtitles |

### 3.2 Request Format

```json
POST /api/subtitles
Content-Type: application/json
X-API-Key: your-api-key (optional)

{
  "video_id": "dQw4w9WgXcQ",
  "language": "en",
  "clean_for_ai": true
}
```

Or with URL:

```json
{
  "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
  "language": "zh-Hans"
}
```

### 3.3 Response Format

```json
{
  "success": true,
  "video_id": "dQw4w9WgXcQ",
  "title": "Rick Astley - Never Gonna Give You Up",
  "language": "en",
  "extraction_method": "youtube-transcript-api",
  "subtitle_count": 42,
  "duration_ms": 1234,
  "cached": false,
  "subtitles": [
    { "start": 0.5, "duration": 2.0, "text": "We are no strangers to love" }
  ],
  "plain_text": "We are no strangers to love You know the rules...",
  "proxy_used": null
}
```

Note: `proxy_used` is `null` for direct connections, or `"ip:port"` when proxy was used.

---

## 4. Security Hardening

### 4.1 Input Validation

```python
# Video ID: 11 alphanumeric characters only
VIDEO_ID_PATTERN = r'^[a-zA-Z0-9_-]{11}$'

# URL: Whitelist domains
ALLOWED_DOMAINS = ['youtube.com', 'youtu.be', 'youtube-nocookie.com']

# Timeout: 30s hard limit
EXTRACTION_TIMEOUT = 30
```

### 4.2 Container Security

```yaml
security:
  - non-root user (UID 1000)
  - no sudo/elevation
  - 30s process timeout
  - memory limit 512MB
  - read-only /app (optional)
```

### 4.3 Rate Limiting

| Level      | Limit      | Implementation      |
| ---------- | ---------- | ------------------- |
| Per-IP     | 30 req/min | In-memory TTL cache |
| Concurrent | 5 max      | Counter             |
| Burst      | 5 req/10s  | Token bucket        |

---

## 5. Caching Strategy

### 5.1 In-Memory Cache (Simplified)

```python
# TTL: 1 hour
# Max Size: 500 videos
# Eviction: LRU
cache = TTLCache(maxsize=500, ttl=3600)
```

### 5.2 Cache Key

```
{video_id}:{language}
```

### 5.3 Expected Hit Rate

| Scenario                  | Hit Rate |
| ------------------------- | -------- |
| Same video, same language | 100%     |
| Repeated requests         | 85%+     |
| Cold start                | 0%       |

---

## 6. Deployment Plan

### 6.1 File Structure (Final)

```
/opt/docker-projects/heavy-tasks/youtube-subtitle-api/
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── requirements.txt
├── .env
├── .env.example
├── config/
│   └── proxies.txt       # Proxy list (ip:port,user,pass or ip:port:user:pass)
├── logs/
└── app/
    ├── __init__.py
    ├── main.py
    └── services/
        ├── __init__.py
        ├── subtitle_service.py
        └── proxy_manager.py  # Proxy rotation with failure tracking
```

### 6.2 Deployment Commands

```bash
# Local: Sync to server
rsync -avz --exclude 'logs' --exclude '.env' \
  /Volumes/SSD/skills/server-ops/vps/107.174.42.198/heavy-tasks/YouTube-Subtitle-API/simple/ \
  root@107.174.42.198:/opt/docker-projects/heavy-tasks/youtube-subtitle-api/

# Server: Deploy
ssh root@107.174.42.198
cd /opt/docker-projects/heavy-tasks/youtube-subtitle-api
make init      # Create .env
vim .env       # Set API_KEY
make deploy    # Build + Run
make health    # Verify
```

### 6.3 Makefile Commands

| Command       | Description        |
| ------------- | ------------------ |
| `make init`   | Initialize .env    |
| `make build`  | Build Docker image |
| `make deploy` | Validate + Deploy  |
| `make logs`   | Stream logs        |
| `make down`   | Stop container     |
| `make health` | Health check       |
| `make test`   | Test extraction    |

---

## 7. Configuration

### 7.1 Environment Variables

```bash
# .env
API_KEY=your-secure-api-key-here
ALLOWED_ORIGINS=*
RATE_LIMIT_PER_MINUTE=30
MAX_CONCURRENT=5
CACHE_TTL_SECONDS=3600
CACHE_MAX_SIZE=500
EXTRACTION_TIMEOUT=30
FALLBACK_ENABLED=true
LOG_LEVEL=INFO

# Proxy Configuration (Direct First, Proxy on Failure)
USE_PROXY=true                    # Enable proxy rotation on failure
PROXY_COOLDOWN_SECONDS=60         # Cooldown after proxy failure
PROXY_MAX_FAILURES=3              # Max failures before proxy cooldown
```

### 7.2 Network

```yaml
networks:
  proxy-tier:
    external: true
    name: nginx-proxy_default
```

---

## 8. Monitoring

### 8.1 Health Endpoint

```json
GET /health

{
  "status": "healthy",
  "cache_size": 42,
  "cache_hit_rate": 0.85,
  "uptime_seconds": 3600,
  "proxy_stats": {
    "total": 120,
    "available": 118,
    "unavailable": 2,
    "failure_rate": 0.02
  }
}
```

### 8.2 Logs

```bash
# View logs
make logs

# Log format (structured JSON)
{"timestamp": "2025-12-30T18:45:00.123Z", "level": "INFO", "event": "extraction_success", "video_id": "dQw4w9WgXcQ", "method": "youtube-transcript-api", "duration_ms": 1234}
```

---

## 9. Cost Analysis

| Item               | Monthly Cost  |
| ------------------ | ------------- |
| VPS (shared)       | $0            |
| Memory (256-512MB) | $0            |
| Storage (logs)     | < $1          |
| **Total**          | **~$2/month** |

---

## 10. Risk Mitigation

### 10.1 YouTube Blocking

| Risk Level | Trigger       | Mitigation                     |
| ---------- | ------------- | ------------------------------ |
| Low        | < 100 req/min | Normal operation (direct)      |
| Medium     | 403 errors    | Proxy rotation (auto-failover) |
| High       | All proxies   | yt-dlp fallback + proxy        |

### 10.2 Proxy Strategy (Implemented)

**Strategy**: Direct First, Proxy on Failure

```
1. Try youtube-transcript-api with server IP (direct)
2. On 403/429/blocked → Retry with proxy from pool (120+ proxies)
3. On failure → Try yt-dlp with server IP
4. On 403/429/blocked → Retry yt-dlp with proxy
```

**Proxy Pool**: 120+ residential proxies loaded from `config/proxies.txt`

**Formats Supported**:

- `ip:port,user,pass`
- `ip:port:user:pass`

**Failure Tracking**:

- Max 3 failures before cooldown
- 60s cooldown per proxy
- Auto-reset when cooldown expires

---

## 11. Future Enhancements

| Priority | Feature                  | Effort | Status       |
| -------- | ------------------------ | ------ | ------------ |
| ~~P3~~   | ~~Proxy rotation~~       | ~~4h~~ | ✅ Completed |
| P1       | Persistent cache (Redis) | 2h     | Pending      |
| P2       | Subdomain routing        | 1h     | Pending      |
| P3       | Multi-language support   | 2h     | Pending      |

---

## 12. Checklist

### Pre-Deploy

- [ ] Review code in `/simple/`
- [ ] Set API_KEY in `.env`
- [ ] Verify server connectivity

### Deploy

- [ ] `rsync` files to server
- [ ] `make init` on server
- [ ] `make deploy`
- [ ] `make health` - verify

### Post-Deploy

- [ ] Test with real video ID
- [ ] Monitor logs for errors
- [ ] Document API key location

---

## Quick Start (Copy-Paste)

```bash
# 1. Sync to server
rsync -avz /Volumes/SSD/skills/server-ops/vps/107.174.42.198/heavy-tasks/YouTube-Subtitle-API/simple/ \
  root@107.174.42.198:/opt/docker-projects/heavy-tasks/youtube-subtitle-api/

# 2. SSH and deploy
ssh root@107.174.42.198 << 'EOF'
cd /opt/docker-projects/heavy-tasks/youtube-subtitle-api
make init
echo "API_KEY=yt-sub-$(openssl rand -hex 16)" >> .env
make deploy
sleep 5
make health
EOF

# 3. Test
curl -X POST http://107.174.42.198:8020/api/subtitles \
  -H "Content-Type: application/json" \
  -d '{"video_id": "dQw4w9WgXcQ"}'
```

---

**Document Version**: 1.0
**Created**: 2025-12-30
**Source**: Multi-LLM Meeting (Codex, Gemini, BigModel)
