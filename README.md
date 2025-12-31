# YouTube Subtitle API

Production-grade YouTube subtitle extraction API (FastAPI) with async processing (RQ), a 3-tier cache (memory -> Redis -> Postgres), metrics, admin tooling, and webhook support.

## Features

- **Dual-Engine Extraction**: youtube-transcript-api (fast) + yt-dlp fallback (handles restricted videos)
- **Async Processing**: RQ job queue for background extraction
- **3-Tier Cache**: In-memory LRU -> Redis -> PostgreSQL
- **Webhook Notifications**: Optional callbacks when jobs complete
- **Security**: API key or JWT authentication for admin endpoints
- **Rate Limiting**: Redis-based per-IP rate limiting
- **Metrics**: Prometheus metrics endpoint
- **CORS**: Configurable allowed origins (fail-closed by default)

## Local development (recommended)

```bash
make local-up
make local-test
```

- API: `http://localhost:8010`
- OpenAPI: `http://localhost:8010/docs`

## API usage

### Basic subtitle extraction

```bash
curl -X POST http://localhost:8010/api/v1/subtitles \
  -H "Content-Type: application/json" \
  -d '{"video_url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"en","clean_for_ai":true}'
```

### With webhook notification

```bash
curl -X POST http://localhost:8010/api/v1/subtitles \
  -H "Content-Type: application/json" \
  -d '{
    "video_url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "language":"en",
    "webhook_url":"https://your-domain.com/webhook"
  }'
```

Webhook payload includes HMAC signature for verification (if `WEBHOOK_SECRET` is configured).

## Frontend (Cloudflare Pages)

The repository includes a standalone frontend in `frontend/` designed for **Cloudflare Pages**.

- Local dev: `cd frontend && npm i && npm run dev`
- Production: deploy `frontend/` to Pages and set `BACKEND_BASE_URL` (and optional `BACKEND_API_KEY`).

See `frontend/README.md` for exact Pages settings.

## Environment configuration

Copy `.env.example` to `.env` and configure:

```bash
# Required for admin endpoints
API_KEY=your-api-key-here
# or
JWT_SECRET=your-jwt-secret-here

# Required for CORS to work
ALLOWED_ORIGINS=https://your-domain.com

# Webhook signature verification (optional)
WEBHOOK_SECRET=your-webhook-secret-here
```

## Documentation

All documentation lives in `docs/`:

- `docs/QUICK_START.md` - Getting started guide
- `docs/API-README.md` - API documentation
- `docs/DEPLOYMENT.md` - Production deployment guide
- `docs/PRODUCTION_CHECKLIST.md` - Pre-deployment checklist

## Notes

- `simple/` is a legacy minimal variant kept for reference
