# Frontend (Cloudflare Pages)

This directory contains a static frontend (Vite + TypeScript) intended to be deployed separately from the FastAPI backend.

## Local development

- Install deps: `npm i`
- Run dev server (direct to backend): `VITE_API_BASE_URL=http://localhost:8010 npm run dev`
  - If you omit `VITE_API_BASE_URL`, the app will call same-origin `/api/*` (useful when running behind a proxy).

## Cloudflare Pages deployment

**Recommended setup:** use Pages Functions to proxy `/api/*` so browsers never see backend secrets and you avoid CORS.

Cloudflare Pages settings:

- **Root directory:** `frontend`
- **Build command:** `npm run build`
- **Build output directory:** `dist`
- **Functions directory:** `functions` (auto-detected)

Pages environment variables:

- `BACKEND_BASE_URL` (required) — e.g. `https://api.example.com`
- `BACKEND_API_KEY` (optional) — sent as `X-API-Key` to the backend by the proxy function

After deployment:

- The frontend calls `/api/*` (same-origin).
- Pages Functions proxy to the backend:
  - `/api/*` → `${BACKEND_BASE_URL}/api/*`
  - `/docs/*` → `${BACKEND_BASE_URL}/docs/*`
  - `/openapi.json` → `${BACKEND_BASE_URL}/openapi.json`
  - `/health` → `${BACKEND_BASE_URL}/health`
  - `/metrics` → `${BACKEND_BASE_URL}/metrics`

SEO/static:

- `robots.txt` and `sitemap.xml` are served by Pages Functions so they include the correct site origin.
