# Project Review (PM / Architect / PSEO)

Date: 2025-12-30

This document turns a full-code review into an execution checklist for production readiness.

## /pm (Product)

**Primary user:** developers/agents who need subtitles + plain text fast and reliably.

**Definition of done (release):**

- `POST /api/subtitles` returns:
  - `200` with full payload on cache hit
  - `202` with `job_id` on cache miss
- `GET /api/job/{job_id}` returns stable statuses and includes `result` when finished.
- `GET /api/subtitles/{video_id}` returns cached result or `404` if missing.
- Rate limiting is enforced with predictable `429` + `Retry-After`.
- Auth is consistent:
  - Public by default in development.
  - In production, `API_KEY` and/or `JWT_SECRET` can lock down endpoints.
- Docs are accurate and copy/paste-able:
  - at least one `curl` example for each endpoint
  - clear env var list for deploy

## /architect (Backend + Deploy)

**High-risk findings to fix first:**

- Dockerfiles build wheels with `--no-deps` but install only local wheels → missing transitive deps in runtime images.
- API container command hardcodes `--workers 1` → ignores `WORKERS` env and production compose config.
- Missing `.dockerignore` → Docker build context can include `frontend/node_modules` (very slow builds).

**Reliability/scale:**

- Avoid Redis `KEYS` in production paths (use `SCAN`).
- Split health endpoints:
  - `/health` (dependency checks, readiness)
  - `/live` (process liveness, always 200 if running)
- Keep schema handling consistent:
  - migrations via Alembic for production
  - optional `create_all` only for development/local stack

## /pseo (Frontend + SEO)

**Goal:** a lightweight marketing/dev-tool landing page that ranks for “YouTube subtitles API” and converts to API usage.

**Must-have technical SEO:**

- `robots.txt` + `sitemap.xml`
- Canonical URL support (configurable via env at build time)
- OpenGraph + Twitter cards with a share image
- Fast performance (no frameworks, no heavy deps)

**Content structure (minimal):**

- Hero: “Extract YouTube subtitles via API”
- “How it works” (cache hit vs async job)
- Copy/paste `curl` examples
- Links to `/docs` and `/openapi.json`

## Execution Order

1. Fix Docker/build + env mismatches (unblocks real testing + deploy)
2. Backend correctness + safety (rate limit, cache patterns, schema policy)
3. Frontend UX + SEO assets (robots/sitemap/meta/share image)
4. Cleanup (remove legacy artifacts, tighten ignore files)
5. Run `make local-up` + `make local-test` + `npm run build` and verify manually
