# Multi-LLM Meeting Summary

> Date: 2025-12-30
> Mode: /meet (Raw Resonance)
> Participants: Codex (Claude), Gemini, BigModel (GLM-4)

---

## Meeting Objective

Deploy a YouTube Subtitle API on VPS 107.174.42.198 using the proposed vibing-sub code structure.

---

## Model Perspectives

### Codex (Claude) - Engineering Focus

**Key Insights:**

- Recommended `standalone-apps/` initially, but acknowledged `heavy-tasks/` valid for cost
- Created complete working code in `/simple/` subdirectory
- Emphasized security hardening for yt-dlp (RCE history)
- Suggested non-root user, 30s timeout, video ID regex validation

**Deliverables:**

- Full application code (main.py, subtitle_service.py)
- docker-compose.yml with resource limits
- Makefile with standard commands
- README with API documentation

### Gemini - Architecture Focus

**Key Insights:**

- Recommended `heavy-tasks/` for I/O-bound workload
- Proposed 3-tier cache: Memory → Redis → PostgreSQL
- Emphasized observability: Prometheus metrics, structured logging
- Suggested horizontal scaling model (Phase 1-3)

**Deliverables:**

- Detailed ARCHITECTURE.md (666 lines)
- Scaling roadmap
- Cost analysis
- Alerting rules

### BigModel (GLM-4) - Pragmatic/Cost Focus

**Key Insights:**

- Strong preference for `heavy-tasks/` (cost optimization)
- Warned about Alpine musl compatibility issues
- Emphasized Chinese developer common pitfalls
- Recommended starting simple, upgrade when needed

**Deliverables:**

- Cost breakdown (RMB perspective)
- Proxy strategy for YouTube blocking
- Database schema template
- Complete docker-compose.yml

---

## Consensus Points (All 3 Agree)

| Decision    | Consensus                                        |
| ----------- | ------------------------------------------------ |
| Base Image  | `python:3.10/3.11-slim-bookworm` (not Alpine)    |
| Dual Engine | youtube-transcript-api → yt-dlp fallback         |
| Caching     | Start with in-memory, upgrade to Redis if needed |
| Rate Limit  | 30 req/min per IP                                |
| Security    | Non-root user, video ID validation, 30s timeout  |
| Restart     | `unless-stopped` policy                          |

---

## Disagreement Points

| Topic          | Codex           | Gemini      | BigModel    | Resolution                   |
| -------------- | --------------- | ----------- | ----------- | ---------------------------- |
| Placement      | standalone-apps | heavy-tasks | heavy-tasks | **heavy-tasks** (2/3)        |
| Python Version | 3.10            | 3.13        | 3.11        | **3.10** (safest)            |
| Cache Backend  | In-memory       | 3-tier      | In-memory   | **In-memory** (start simple) |
| Port           | 8020            | 8010        | 8000        | **8020** (avoid conflicts)   |

---

## Architecture Diagram (Merged)

```
┌─────────────────────────────────────────────────────────────┐
│                         Client                               │
│                    POST /api/subtitles                       │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    nginx-proxy_default                       │
│              (optional: subtitle-api.domain.com)             │
└────────────────────────────┬────────────────────────────────┘
                             │ :8020
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                 FastAPI Container                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │
│  │ Rate Limit  │  │   Cache     │  │  Extractor  │          │
│  │ (in-memory) │  │ (TTLCache)  │  │ (dual-eng)  │          │
│  └─────────────┘  └─────────────┘  └──────┬──────┘          │
│                                           │                  │
│  ┌────────────────────────────────────────┴───────────────┐ │
│  │                                                         │ │
│  │  ┌──────────────────┐      ┌──────────────────┐        │ │
│  │  │ youtube-trans-   │  OR  │     yt-dlp       │        │ │
│  │  │ cript-api (3s)   │  ──► │   fallback (15s) │        │ │
│  │  └──────────────────┘      └──────────────────┘        │ │
│  │                                                         │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
                        YouTube.com
```

---

## Risk Assessment (Merged)

| Risk              | Probability      | Impact | Mitigation                     |
| ----------------- | ---------------- | ------ | ------------------------------ |
| YouTube IP ban    | Low (30 req/min) | Medium | yt-dlp fallback + proxy        |
| yt-dlp RCE        | Very Low         | High   | Non-root, timeout, version pin |
| Memory exhaustion | Low              | Medium | 512MB limit, LRU cache         |
| Rate limit abuse  | Medium           | Low    | Per-IP limiting                |

---

## Cost Projection

| Scenario                          | Monthly Cost |
| --------------------------------- | ------------ |
| Minimal usage (< 1000 req/day)    | ~$2          |
| Moderate usage (< 10,000 req/day) | ~$5          |
| If proxy needed                   | +$50         |
| If Redis caching added            | +$0 (shared) |

---

## Implementation Priority

1. **P0 - Core API** (Codex deliverable - DONE)
   - FastAPI + dual-engine extraction
   - In-memory caching
   - Rate limiting

2. **P1 - Deploy to Server**
   - rsync files
   - Configure .env
   - make deploy

3. **P2 - Monitoring** (Gemini recommendation)
   - Structured logging (already included)
   - Health endpoint (already included)

4. **P3 - Future**
   - Redis persistent cache
   - Proxy rotation
   - Subdomain routing

---

## Files Generated

| File                                       | Source    | Status      |
| ------------------------------------------ | --------- | ----------- |
| `/simple/app/main.py`                      | Codex     | Ready       |
| `/simple/app/services/subtitle_service.py` | Codex     | Ready       |
| `/simple/docker-compose.yml`               | Codex     | Ready       |
| `/simple/Dockerfile`                       | Codex     | Ready       |
| `/simple/Makefile`                         | Codex     | Ready       |
| `/simple/requirements.txt`                 | Codex     | Ready       |
| `/ARCHITECTURE.md`                         | Gemini    | Reference   |
| `/docs/GENESIS.md`                         | Synthesis | Master Plan |

---

## Next Action

```bash
# Deploy command (copy-paste ready)
rsync -avz /Volumes/SSD/skills/server-ops/vps/107.174.42.198/heavy-tasks/YouTube-Subtitle-API/simple/ \
  root@107.174.42.198:/opt/docker-projects/heavy-tasks/youtube-subtitle-api/
```

---

**Meeting Status**: Complete
**Decision**: Proceed with `/simple/` implementation
**Owner**: User to approve and deploy
