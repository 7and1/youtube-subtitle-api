#!/bin/bash
#
# Initialize YouTube Subtitle API deployment
# This script sets up environment variables, validates dependencies, and prepares deployment
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'  # No Color

echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}YouTube Subtitle API - Deployment Initialization${NC}"
echo -e "${GREEN}================================================${NC}\n"

# Check prerequisites
echo -e "${YELLOW}Checking prerequisites...${NC}"

# Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}ERROR: Docker not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker installed${NC}"

# Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}ERROR: Docker Compose not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Docker Compose installed${NC}"

# Make
if ! command -v make &> /dev/null; then
    echo -e "${RED}ERROR: Make not installed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Make installed${NC}"

# Check if .env.production exists
if [ ! -f ".env.production" ]; then
    echo -e "\n${YELLOW}Creating .env.production template...${NC}"
    cat > .env.production << 'EOF'
# Service Configuration
SERVICE_NAME=youtube-subtitles-api
ENVIRONMENT=production
LOG_LEVEL=INFO

# API Server
API_HOST=0.0.0.0
API_PORT=8010
WORKERS=2
WORKER_TIMEOUT=30

# Database (Supabase PostgreSQL)
# IMPORTANT: Replace with actual Supabase password
DB_PASSWORD=CHANGE_ME_TO_ACTUAL_PASSWORD
DATABASE_URL=postgresql+asyncpg://postgres:${DB_PASSWORD}@supabase-db:5432/postgres
DB_SCHEMA=youtube_subtitles
DB_POOL_SIZE=10
DB_AUTO_CREATE=false  # Prefer Alembic in production (set true only for dev/local)

# Redis (Job Queue)
REDIS_URL=redis://redis:6379/2
REDIS_QUEUE_NAME=youtube-extraction
REDIS_RESULT_TTL=86400

# YouTube Configuration
YT_EXTRACTION_TIMEOUT=30
YT_RETRY_MAX_ATTEMPTS=3
YT_RETRY_BACKOFF_FACTOR=2
# YT_PROXY_URLS=  # Optional: comma-separated proxy URLs

# Rate Limiting
RATE_LIMIT_REQUESTS_PER_MINUTE=30
RATE_LIMIT_BURST_SIZE=5
CACHE_TTL_MINUTES=1440

# Monitoring
PROMETHEUS_ENABLED=true
# SENTRY_DSN=  # Optional: Sentry error tracking

# Security
JWT_SECRET=CHANGE_ME_TO_SECURE_SECRET
API_KEY_HEADER_NAME=X-API-Key
ALLOWED_ORIGINS=*

# Worker Configuration
WORKER_CONCURRENCY=2
WORKER_PREFETCH_MULTIPLIER=1
WORKER_DB_POOL_SIZE=5
EOF
    echo -e "${GREEN}✓ .env.production created${NC}"
    echo -e "${YELLOW}WARNING: Update .env.production with actual credentials before deploying${NC}"
else
    echo -e "${GREEN}✓ .env.production exists${NC}"
fi

# Validate docker-compose.yml
echo -e "\n${YELLOW}Validating docker-compose.yml...${NC}"
if docker-compose config > /dev/null 2>&1; then
    echo -e "${GREEN}✓ docker-compose.yml is valid${NC}"
else
    echo -e "${RED}ERROR: docker-compose.yml is invalid${NC}"
    exit 1
fi

# Check network availability
echo -e "\n${YELLOW}Checking Docker networks...${NC}"

for network in nginx-proxy_default supabase_default redis_default; do
    if docker network ls | grep -q "^[a-f0-9].*$network"; then
        echo -e "${GREEN}✓ Network '$network' exists${NC}"
    else
        echo -e "${RED}ERROR: Network '$network' not found${NC}"
        echo -e "${YELLOW}  Ensure these services are running on the VPS${NC}"
        exit 1
    fi
done

# Check if containers can connect to dependencies
echo -e "\n${YELLOW}Checking dependency connectivity...${NC}"

# Test Redis
if docker run --rm --network=redis_default redis:latest redis-cli -h redis ping &> /dev/null; then
    echo -e "${GREEN}✓ Redis is accessible${NC}"
else
    echo -e "${RED}ERROR: Cannot connect to Redis${NC}"
    exit 1
fi

# Test PostgreSQL
if docker run --rm --network=supabase_default postgres:latest pg_isready -h supabase-db -U postgres &> /dev/null; then
    echo -e "${GREEN}✓ PostgreSQL is accessible${NC}"
else
    echo -e "${RED}ERROR: Cannot connect to PostgreSQL${NC}"
    exit 1
fi

# Validate credentials
echo -e "\n${YELLOW}Validating credentials...${NC}"

source .env.production

if [ "$DB_PASSWORD" == "CHANGE_ME_TO_ACTUAL_PASSWORD" ]; then
    echo -e "${RED}ERROR: DB_PASSWORD not set in .env.production${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Database password configured${NC}"

if [ "$JWT_SECRET" == "CHANGE_ME_TO_SECURE_SECRET" ]; then
    echo -e "${RED}ERROR: JWT_SECRET not set in .env.production${NC}"
    exit 1
fi
echo -e "${GREEN}✓ JWT secret configured${NC}"

# Summary
echo -e "\n${GREEN}================================================${NC}"
echo -e "${GREEN}Initialization Complete!${NC}"
echo -e "${GREEN}================================================${NC}\n"

echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review .env.production and confirm all settings"
echo "2. Run: ${GREEN}make build${NC}"
echo "3. Run: ${GREEN}make deploy${NC}"
echo "4. Run: ${GREEN}make health${NC}"
echo ""
echo -e "${YELLOW}For detailed information:${NC}"
echo "- See ARCHITECTURE.md for design decisions"
echo "- See DEPLOYMENT.md for step-by-step guide"
echo "- Run: ${GREEN}make help${NC} for available commands"
echo ""
