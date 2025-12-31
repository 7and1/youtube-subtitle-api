# Production Deployment Checklist

Use this checklist when deploying the YouTube Subtitle API to production environments.

## Pre-Deployment Preparation

### 1. Security Configuration

- [ ] Generate strong `API_KEY` using: `openssl rand -base64 32`
- [ ] Generate strong `JWT_SECRET` using: `openssl rand -base64 32`
- [ ] Set `ALLOWED_ORIGINS` to specific frontend domains only (never `*` in production)
- [ ] Set `RATE_LIMIT_FAIL_OPEN=false` to enforce rate limiting
- [ ] Generate `WEBHOOK_SECRET` if using webhook notifications: `openssl rand -base64 32`
- [ ] Verify `ENVIRONMENT=production` is set

### 2. Database Preparation

- [ ] Backup existing database before schema changes:
  ```bash
  pg_dump -h supabase-db -U postgres -n youtube_subtitles > backup_$(date +%Y%m%d).sql
  ```
- [ ] Verify `DB_SCHEMA` is set to `youtube_subtitles` (or your custom schema)
- [ ] Set `DB_AUTO_CREATE=false` to prefer Alembic migrations
- [ ] Verify database user has proper permissions

### 3. Infrastructure Verification

- [ ] Confirm Redis is accessible: `redis-cli -n 2 ping`
- [ ] Confirm PostgreSQL is accessible: `pg_isready -h supabase-db -U postgres`
- [ ] Verify nginx-proxy network is available: `docker network ls | grep nginx-proxy_default`
- [ ] Verify supabase network is available: `docker network ls | grep supabase_default`
- [ ] Verify redis network is available: `docker network ls | grep redis_default`

### 4. Environment File

- [ ] Copy `.env.example` to `.env.production`
- [ ] Fill in all required values (database password, secrets, etc.)
- [ ] Verify no placeholder values remain
- [ ] Ensure `.env` and `.env.production` are in `.gitignore`

## Deployment Steps

### 5. Build & Deploy

- [ ] Pull latest code: `git pull origin main`
- [ ] Build Docker images: `make build`
- [ ] Validate configuration: `make validate`
- [ ] Deploy services: `make deploy`
- [ ] Verify containers are running: `make ps`

### 6. Database Migrations

- [ ] Run migrations: `docker-compose exec api alembic upgrade head`
- [ ] Verify migration success: `docker-compose exec api alembic current`
- [ ] Check tables created: `docker-compose exec api psql $DATABASE_URL -c "\dt youtube_subtitles.*"`

### 7. Health Verification

- [ ] Check API health: `curl http://localhost:8010/health`
- [ ] Verify response contains:
  - `"status": "healthy"`
  - `"api": "ready"`
  - `"redis": "connected"`
  - `"postgres": "connected"`
- [ ] Check metrics endpoint: `curl http://localhost:8010/metrics`

### 8. Authentication Testing

- [ ] Test admin endpoint WITHOUT auth (should fail):
  ```bash
  curl -X POST http://localhost:8010/api/v1/admin/cache/clear
  # Expected: 500 or 401 with auth required message
  ```
- [ ] Test admin endpoint WITH API key (should succeed):
  ```bash
  curl -X POST http://localhost:8010/api/v1/admin/cache/clear \
    -H "X-API-Key: YOUR_API_KEY"
  # Expected: 200 with cache cleared response
  ```
- [ ] Test admin endpoint WITH JWT token (should succeed):
  ```bash
  curl -X POST http://localhost:8010/api/v1/admin/cache/clear \
    -H "Authorization: Bearer YOUR_JWT_TOKEN"
  # Expected: 200 with cache cleared response
  ```

### 9. Functionality Testing

- [ ] Test subtitle extraction:
  ```bash
  curl -X POST http://localhost:8010/api/v1/subtitles \
    -H "Content-Type: application/json" \
    -H "X-API-Key: YOUR_API_KEY" \
    -d '{"video_url":"https://www.youtube.com/watch?v=dQw4w9WgXcQ","language":"en"}'
  ```
- [ ] Test webhook callback (if configured)
- [ ] Test rate limiting (make 30+ requests in quick succession)
- [ ] Test CORS from your frontend domain

## Post-Deployment

### 10. Monitoring Setup

- [ ] Configure Prometheus to scrape `/metrics` endpoint
- [ ] Set up alerts for:
  - Error rate > 1%
  - Response time p95 > 5s
  - Queue depth > 100
  - Worker failure rate > 5%
- [ ] Verify logs are being captured: `make logs`
- [ ] Check for any ERROR or WARNING messages

### 11. Resource Limits

- [ ] Monitor container resource usage: `make stats`
- [ ] Verify memory usage is within limits (API: 512MB, Worker: 512MB)
- [ ] Adjust limits if needed based on actual usage
- [ ] Consider scaling workers if queue depth is consistently high

### 12. Documentation

- [ ] Update deployment documentation with any custom configurations
- [ ] Document any deviations from standard setup
- [ ] Share API credentials securely with frontend team

## Security Hardening

### 13. Network Security

- [ ] Verify only necessary ports are exposed
- [ ] Ensure nginx-proxy is handling SSL termination
- [ ] Check firewall rules allow only necessary traffic
- [ ] Verify database is not directly accessible from internet

### 14. Access Control

- [ ] Limit admin endpoint access to internal networks only
- [ ] Use separate API keys for different environments
- [ ] Rotate secrets periodically (document rotation procedure)
- [ ] Audit logs for unauthorized access attempts

## Backup & Recovery

### 15. Backup Strategy

- [ ] Set up automated daily database backups
- [ ] Test backup restoration procedure
- [ ] Document backup location and retention policy
- [ ] Set up off-site backup replication

### 16. Rollback Plan

- [ ] Tag current Docker image before deploying: `docker tag youtube-subtitles-api:latest youtube-subtitles-api:backup-$(date +%Y%m%d)`
- [ ] Document rollback steps in runbook
- [ ] Test rollback procedure in staging environment

## Performance Tuning

### 17. Caching Strategy

- [ ] Monitor cache hit ratio via metrics
- [ ] Adjust `CACHE_TTL_MINUTES` based on content change frequency
- [ ] Tune `MEMORY_CACHE_MAX_SIZE` based on available memory
- [ ] Consider Redis persistence if cache warm-up time is long

### 18. Worker Scaling

- [ ] Start with 2 workers, scale based on queue depth
- [ ] Monitor worker CPU utilization
- [ ] Scale using: `make scale WORKERS=4`
- [ ] Consider dedicated worker nodes for high-traffic deployments

## Ongoing Operations

### 19. Log Management

- [ ] Set up log aggregation (e.g., Loki, ELK)
- [ ] Configure log rotation (already set to 20MB x 3 files)
- [ ] Monitor log volume and adjust retention as needed
- [ ] Set up alerts for critical errors in logs

### 20. Health Monitoring

- [ ] Set up external monitoring (e.g., Uptime Kuma, Pingdom)
- [ ] Configure alerts for service downtime
- [ ] Monitor queue depth and processing time
- [ ] Track API response times and error rates

## Sign-Off

- [ ] Deployment completed by: \***\*\*\*\*\***\_\_\_\***\*\*\*\*\*** Date: **\_\_\_\_**
- [ ] Verification completed by: \***\*\*\*\*\***\_\***\*\*\*\*\*** Date: **\_\_\_\_**
- [ ] Approved for production: \***\*\*\*\*\***\_\_\_\***\*\*\*\*\*** Date: **\_\_\_\_**

## Emergency Contacts

| Role                | Name | Contact |
| ------------------- | ---- | ------- |
| Primary On-Call     |      |         |
| Secondary On-Call   |      |         |
| Database Admin      |      |         |
| Infrastructure Lead |      |         |
