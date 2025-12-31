.PHONY: help build validate deploy logs down ps health test clean lint format

PROJECT_NAME := youtube-subtitles
DOCKER_COMPOSE := docker-compose -f docker-compose.yml -p $(PROJECT_NAME)
DOCKER_COMPOSE_LOCAL := docker-compose -f docker-compose.local.yml -p $(PROJECT_NAME)-local

help:
	@echo "YouTube Subtitle API - Makefile Commands"
	@echo "========================================"
	@echo "  make build       - Build Docker image"
	@echo "  make validate    - Validate docker-compose.yml"
	@echo "  make deploy      - Deploy containers (docker-compose up -d)"
	@echo "  make logs        - Stream logs from running containers"
	@echo "  make down        - Stop and remove containers"
	@echo "  make ps          - Show running containers"
	@echo "  make health      - Check service health status"
	@echo "  make test        - Run unit tests"
	@echo "  make lint        - Run code linter (ruff)"
	@echo "  make format      - Format code (black)"
	@echo "  make clean       - Remove containers and images"
	@echo ""
	@echo "Local dev (no external networks):"
	@echo "  make local-up    - Start local API+worker+deps"
	@echo "  make local-down  - Stop local stack"
	@echo "  make local-logs  - Tail local logs"
	@echo "  make local-test  - Run pytest in local API container"

build:
	@echo "Building Docker image..."
	$(DOCKER_COMPOSE) build --no-cache api worker
	@echo "Build complete"

validate:
	@echo "Validating docker-compose.yml..."
	docker-compose -f docker-compose.yml config > /dev/null && echo "Validation successful"

deploy: validate
	@echo "Deploying YouTube Subtitle API..."
	$(DOCKER_COMPOSE) up -d api worker
	@echo "Deployment complete. Check status with 'make ps'"
	@sleep 2
	@make health

logs:
	@echo "Streaming logs from all containers..."
	$(DOCKER_COMPOSE) logs -f --timestamps

down:
	@echo "Stopping containers..."
	$(DOCKER_COMPOSE) down
	@echo "Containers stopped"

ps:
	@echo "Running containers:"
	$(DOCKER_COMPOSE) ps

health:
	@echo "Checking service health..."
	@curl -s -f http://localhost:8010/health > /dev/null && \
		echo "API Service: HEALTHY (HTTP 200)" || \
		echo "API Service: UNHEALTHY or not responding"
	@redis-cli ping > /dev/null 2>&1 && \
		echo "Redis: AVAILABLE" || \
		echo "Redis: UNAVAILABLE (check connection)"
	@pg_isready -h localhost -U postgres > /dev/null 2>&1 && \
		echo "PostgreSQL: AVAILABLE" || \
		echo "PostgreSQL: UNAVAILABLE (check connection)"

# Scale worker instances (e.g., make scale WORKERS=4)
scale:
	@echo "Scaling worker to $(WORKERS) instances..."
	$(DOCKER_COMPOSE) up -d --scale worker=$(WORKERS)

# Development commands
test:
	@echo "Running tests..."
	pytest tests/ -v --cov=src --cov-report=html

lint:
	@echo "Running linter..."
	ruff check src/ tests/ main.py worker.py

format:
	@echo "Formatting code..."
	black src/ tests/ main.py worker.py

# Stop specific services for maintenance
stop-api:
	$(DOCKER_COMPOSE) stop api

stop-workers:
	$(DOCKER_COMPOSE) stop worker

restart:
	@echo "Restarting services..."
	$(DOCKER_COMPOSE) restart api worker

# View container resource usage
stats:
	docker stats --no-stream $(PROJECT_NAME)-api $(PROJECT_NAME)-worker

# Clean up (destructive)
clean:
	@echo "WARNING: This will remove containers, volumes, and images"
	@echo "Press Ctrl+C to cancel, or wait 5 seconds..."
	@sleep 5
	$(DOCKER_COMPOSE) down -v
	$(DOCKER_COMPOSE) rmi -f api
	@echo "Cleanup complete"

# Local stack (Redis + Postgres included)
local-up:
	$(DOCKER_COMPOSE_LOCAL) up -d --build
	@echo "Local API: http://localhost:$${LOCAL_API_PORT:-8010} (API_KEY=test)"

local-down:
	$(DOCKER_COMPOSE_LOCAL) down -v

local-logs:
	$(DOCKER_COMPOSE_LOCAL) logs -f --timestamps

local-test:
	$(DOCKER_COMPOSE_LOCAL) run --rm api pytest -q

# Database migrations
migrate-up:
	@echo "Running database migrations..."
	alembic upgrade head

migrate-down:
	@echo "Reversing latest migration..."
	alembic downgrade -1

# Admin operations
admin-clear-cache:
	@echo "Clearing Redis cache..."
	redis-cli -n 2 FLUSHDB
	@echo "Cache cleared"

admin-queue-stats:
	@echo "Job queue statistics:"
	redis-cli -n 2 INFO

# Monitoring shortcuts
watch-metrics:
	watch -n 2 'curl -s http://localhost:8010/metrics | head -50'

.PHONY: scale stop-api stop-workers restart stats migrate-up migrate-down admin-clear-cache admin-queue-stats watch-metrics
