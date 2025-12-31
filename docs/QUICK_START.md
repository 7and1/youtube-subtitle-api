# YouTube Subtitle API - Quick Start Guide

**5-minute setup for development/testing**

## 1. Prerequisites Check

```bash
# Verify dependencies are installed
docker --version       # Docker 24+
docker-compose --version  # Docker Compose 2+
make --version        # GNU Make 4+
curl --version        # For testing
```

## 2. Initial Setup

```bash
cd /opt/docker-projects/heavy-tasks/YouTube-Subtitle-API

# Make init script executable and run
chmod +x init.sh
./init.sh

# This will:
# - Validate docker-compose.yml
# - Check network availability
# - Create .env.production template
# - Test Redis/PostgreSQL connectivity
```

## 3. Configure Environment

Edit `.env.production`:

```bash
# CRITICAL: Update these values
DB_PASSWORD=your_actual_supabase_password_here
JWT_SECRET=generate_a_secure_secret_here

# Recommended for production (use Alembic migrations)
DB_AUTO_CREATE=false
```

To generate JWT secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## 4. Build & Deploy

```bash
# Build Docker images
make build

# Deploy services (starts API + 2 workers)
make deploy

# Wait 10 seconds for containers to start
sleep 10

# Check health
make health
```

Expected output:

```
API Service: HEALTHY (HTTP 200)
Redis: AVAILABLE
PostgreSQL: AVAILABLE
```

## 5. Test API

```bash
# Get service info
curl http://localhost:8010/

# Expected:
# {
#   "service": "YouTube Subtitle API",
#   "version": "1.0.0",
#   "docs": "/docs"
# }

# View API documentation
open http://localhost:8010/docs

# Test extraction (will queue job)
curl -X POST http://localhost:8010/api/subtitles \
  -H "Content-Type: application/json" \
  -d '{"video_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'

# View logs
make logs

# View running containers
make ps
```

## 6. Common Commands

```bash
# View logs
make logs

# Scale workers
make scale WORKERS=4

# Clear cache
make admin-clear-cache

# Health check
make health

# View metrics
curl http://localhost:8010/metrics

# Stop services (keeps data)
make down

# Full cleanup (removes everything)
make clean
```

## 6.1 Frontend (optional, separate)

Run the standalone frontend (recommended for production-style split):

```bash
cd frontend
npm i
VITE_API_BASE_URL=http://localhost:8010 npm run dev
```

## 7. Access Points

| Service    | URL                           | Purpose                       |
| ---------- | ----------------------------- | ----------------------------- |
| API        | http://localhost:8010         | Main API endpoint             |
| Docs       | http://localhost:8010/docs    | Interactive API documentation |
| Frontend   | http://localhost:5173         | Local UI (Vite dev server)    |
| Health     | http://localhost:8010/health  | Health check                  |
| Metrics    | http://localhost:8010/metrics | Prometheus metrics            |
| Redis      | redis://redis:6379/2          | Job queue & cache             |
| PostgreSQL | supabase-db:5432              | Subtitle storage              |

## 8. Troubleshooting

### Port 8010 already in use

```bash
# Find process using port
lsof -i :8010

# Kill it
kill -9 <PID>

# Or run the local stack on a different port
LOCAL_API_PORT=8011 make local-up
```

### Redis connection failed

```bash
# Check Redis status
docker ps | grep redis

# Restart Redis if needed
docker restart redis
```

### Database connection failed

```bash
# Check PostgreSQL
docker ps | grep postgres

# Verify DB_PASSWORD in .env.production
grep DB_PASSWORD .env.production
```

### Containers won't start

```bash
# Check logs
docker-compose logs

# Validate compose file
docker-compose config

# Rebuild without cache
make build --no-cache
```

## 9. Development Tips

### Live logs with filtering

```bash
# Only errors
docker-compose logs api | grep -i error

# Only specific service
docker-compose logs worker

# With timestamps
docker-compose logs -f --timestamps
```

### Database inspection

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d postgres

# List schemas
\dn

# List tables in youtube_subtitles schema
\dt youtube_subtitles.*

# Check job queue
redis-cli -n 2 LLEN youtube-extraction
```

### Resource monitoring

```bash
# Real-time stats
watch -n 2 'docker stats --no-stream heavy-youtube-subtitles-api'

# One-time snapshot
make stats
```

## 10. Production vs Development

| Aspect     | Development   | Production |
| ---------- | ------------- | ---------- |
| Image      | Debug symbols | Optimized  |
| Logging    | INFO          | WARN       |
| Cache TTL  | 1h            | 24h        |
| Workers    | 2             | 4+         |
| Rate limit | 60/min        | 30/min     |

To use production settings:

```bash
# Copy environment
cp .env.production .env

# Edit for production values
nano .env

# Deploy
make deploy
```

## 11. Next Steps

1. Read **ARCHITECTURE.md** for design decisions
2. Read **DEPLOYMENT.md** for detailed setup
3. Implement worker tasks (Phase 2)
4. Set up monitoring dashboards
5. Load test before production

## 12. Getting Help

```bash
# Show all available commands
make help

# View application logs
make logs

# Check service status
curl http://localhost:8010/status

# Get queue statistics
curl http://localhost:8010/api/admin/queue/stats
```

---

**Quick Links:**

- ARCHITECTURE.md - Complete technical design
- DEPLOYMENT.md - Step-by-step guide
- DEPLOYMENT_SUMMARY.md - Executive overview
- init.sh - Automated initialization

**Support:** Check docker-compose logs for detailed error messages
