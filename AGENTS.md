# Repository Guidelines

## Project Structure & Module Organization

- `main.py`: FastAPI app entrypoint (middleware, routing, metrics).
- `src/`: backend implementation.
  - `src/api/routes/`: HTTP endpoints (`health.py`, `subtitles.py`, `admin.py`).
  - `src/services/`: cache (Redis), DB (Postgres), queue (RQ), rate limiting, extraction logic.
  - `src/worker/`: worker context + job tasks.
- `worker.py`: RQ worker runner (consumes `REDIS_QUEUE_NAME`).
- `frontend/`: Vite + TypeScript frontend for Cloudflare Pages (static assets + Pages Functions proxy).
- `alembic/`: DB migrations; schema defaults to `youtube_subtitles` via `DB_SCHEMA`.
- `docs/`: architecture + deployment notes; source of truth for expected behavior.
- `simple/`: legacy/minimal deployment variant (kept for reference).

## Build, Test, and Development Commands

- Local stack (recommended): `make local-up` (starts Redis + Postgres + API + Worker on `http://localhost:8010`).
- Run tests (inside local stack): `make local-test` or `docker compose -f docker-compose.local.yml exec -T api pytest -q`.
- Stop local stack: `make local-down`.
- Production-style compose (external networks): `make deploy` (uses `docker-compose.yml`).
- Migrations: `make migrate-up` (upgrade head) / `make migrate-down` (rollback one).
- Frontend dev: `cd frontend && npm i && VITE_API_BASE_URL=http://localhost:8010 npm run dev`.
- Frontend build (Pages): `cd frontend && npm run build` (output: `frontend/dist`).

## Coding Style & Naming Conventions

- Python: 4-space indentation, type hints where practical, keep route handlers thin (delegate to `src/services/`).
- Formatting/linting: `black src/ tests/` and `ruff check src/ tests/`.
- Naming: modules `snake_case.py`, classes `PascalCase`, functions/vars `snake_case`.
- Frontend: TypeScript strict mode, prefer small pure helpers, no framework (single-page static app).

## Testing Guidelines

- Framework: `pytest` + `pytest-asyncio`. Name tests `tests/test_*.py`.
- Prefer integration-style tests for queue/cache/DB behavior using `docker-compose.local.yml`.

## Commit & Pull Request Guidelines

- This repo may be used outside Git; if history is unavailable, use Conventional Commits: `feat:`, `fix:`, `docs:`, `chore:`.
- PRs should include: what changed, how to run (`make local-up` + `make local-test`), and an example call to `POST /api/subtitles`.

## Security & Configuration Tips

- Never commit secrets (`.env*`, proxy credentials). Prefer env vars and `config/proxies.txt` for local proxy lists.
- If `API_KEY` is set, requests must include `X-API-Key`. Admin endpoints require admin auth (see `src/services/security.py`).
- Production split: deploy backend separately; deploy `frontend/` to Cloudflare Pages and proxy `/api/*` via Pages Functions using `BACKEND_BASE_URL` (and optional `BACKEND_API_KEY`).
