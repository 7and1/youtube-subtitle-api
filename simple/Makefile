.PHONY: help build validate deploy logs down ps health clean init

PROJECT_NAME := youtube-subtitle-api
DOCKER_COMPOSE := docker-compose -p $(PROJECT_NAME)

help:
	@echo "YouTube Subtitle API - Commands"
	@echo "================================"
	@echo "  make init      - Initialize project (create .env)"
	@echo "  make build     - Build Docker image"
	@echo "  make validate  - Validate docker-compose.yml"
	@echo "  make deploy    - Deploy container"
	@echo "  make logs      - Stream logs"
	@echo "  make down      - Stop container"
	@echo "  make ps        - Show status"
	@echo "  make health    - Check health"
	@echo "  make clean     - Remove container and image"
	@echo "  make test      - Test API endpoint"

init:
	@echo "Initializing project..."
	@if [ ! -f .env ]; then \
		cp .env.example .env 2>/dev/null || echo "API_KEY=change-me-in-production" > .env; \
		echo "Created .env - please set API_KEY"; \
	fi
	@mkdir -p logs
	@echo "Done. Edit .env before deploying."

build:
	@echo "Building Docker image..."
	$(DOCKER_COMPOSE) build --no-cache
	@echo "Build complete"

validate:
	@echo "Validating docker-compose.yml..."
	@docker-compose config > /dev/null && echo "Configuration valid"
	@echo "Checking for named volumes..."
	@if grep -E "^volumes:" docker-compose.yml | grep -v "^  \./"; then \
		echo "WARNING: Found potential named volumes"; \
	fi
	@echo "Validation complete"

deploy: validate
	@echo "Deploying YouTube Subtitle API..."
	@mkdir -p logs
	$(DOCKER_COMPOSE) up -d
	@echo "Waiting for startup..."
	@sleep 3
	@make health
	@echo ""
	@echo "Deployment complete!"
	@echo "API available at: http://localhost:8020"

logs:
	$(DOCKER_COMPOSE) logs -f --timestamps

down:
	@echo "Stopping container..."
	$(DOCKER_COMPOSE) down
	@echo "Stopped"

ps:
	$(DOCKER_COMPOSE) ps

health:
	@echo "Health check..."
	@curl -sf http://localhost:8020/health && echo " OK" || echo " FAILED"

test:
	@echo "Testing subtitle extraction..."
	@curl -s -X POST http://localhost:8020/api/subtitles \
		-H "Content-Type: application/json" \
		-H "X-API-Key: $${API_KEY:-test}" \
		-d '{"video_id": "dQw4w9WgXcQ"}' | head -c 500
	@echo ""

clean:
	@echo "WARNING: This will remove the container and image"
	@read -p "Continue? [y/N] " confirm && [ "$$confirm" = "y" ]
	$(DOCKER_COMPOSE) down --rmi local
	@echo "Cleanup complete"

restart:
	$(DOCKER_COMPOSE) restart

shell:
	$(DOCKER_COMPOSE) exec youtube-subtitle-api /bin/bash
