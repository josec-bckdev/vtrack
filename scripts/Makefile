## VTrack Development Makefile
# Comprehensive development, testing, and operations commands
# Run from project root: make <target>

.PHONY: help

# Default target
.DEFAULT_GOAL := help

##@ Help
help: ## Display this help message
	@echo "VTrack Development Commands"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"; printf "Usage:\n  make \033[36m<target>\033[0m\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)

##@ Docker & Services
build: ## Build the API Docker image (no cache)
	docker compose build api --no-cache

up: ## Start all services in background
	docker compose up -d

down: ## Stop and remove all containers
	docker compose down

rebuild: down build up ## Rebuild API image and restart services

services-start: ## Start all microservices
	./microservices.sh start

services-stop: ## Stop all microservices
	./microservices.sh stop

services-restart: ## Restart all microservices
	./microservices.sh restart

services-status: ## Show status of all services
	./microservices.sh status

services-health: ## Check health of all services
	./microservices.sh health

services-logs: ## Show logs for all services (Ctrl+C to exit)
	./microservices.sh logs

api-logs: ## Show logs for API service only
	./microservices.sh logs api

alert-logs: ## Show logs for alert processor
	./microservices.sh logs alert-processor

services-build: ## Build all microservice images
	./microservices.sh build

services-rebuild: ## Clean rebuild all microservice images
	./microservices.sh rebuild

services-clean: ## Remove all containers and volumes (DESTRUCTIVE)
	./microservices.sh clean

##@ Development Mode (Hot-Reload)
dev-up: ## Start services with dev overrides (hot-reload enabled)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

dev-down: ## Stop dev mode services
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down

dev-start: dev-up ## Alias for dev-up

dev-restart: ## Restart services in dev mode
	docker compose -f docker-compose.yml -f docker-compose.dev.yml restart

dev-restart-api: ## Restart only API in dev mode
	docker compose -f docker-compose.yml -f docker-compose.dev.yml restart api

dev-restart-alert: ## Restart only alert-processor in dev mode
	docker compose -f docker-compose.yml -f docker-compose.dev.yml restart alert-processor

dev-build: ## Build images for dev mode
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build

dev-rebuild: ## Rebuild images in dev mode (no cache)
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache

dev-logs: ## Show logs in dev mode
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f

dev-logs-api: ## Show API logs in dev mode
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f api

dev-logs-alert: ## Show alert-processor logs in dev mode
	docker compose -f docker-compose.yml -f docker-compose.dev.yml logs -f alert-processor

dev-status: ## Show dev mode service status
	docker compose -f docker-compose.yml -f docker-compose.dev.yml ps

##@ Database & Migrations
migrate: ## Run database migrations (upgrade to head)
	./migrate.sh upgrade

migrate-run: ## Run alembic upgrade head inside api container
	docker compose exec api alembic upgrade head

migrate-current: ## Show current migration version
	./migrate.sh current

migrate-history: ## Show migration history
	./migrate.sh history

migrate-status: ## Show detailed migration status
	./migrate.sh status

migrate-create: ## Create new migration (usage: make migrate-create m="description")
	@if [ -z "$(m)" ]; then \
		echo "Please provide a message: make migrate-create m=\"Your message\""; exit 1; \
	fi
	./migrate.sh create "$(m)"

migrate-downgrade: ## Rollback one migration (DESTRUCTIVE)
	./migrate.sh downgrade

migrate-backup: ## Backup database before migration
	./migrate.sh backup

revision: migrate-create ## Alias for migrate-create

current: migrate-current ## Alias for migrate-current

db-shell: ## Open psql shell to the database
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

##@ Monitoring & Queue Management
redis-monitor: ## Monitor Redis queues in real-time
	python ./redis_monitor.py

queue-stats: ## Show Redis queue statistics
	./microservices.sh queue-stats

logs: ## Follow API container logs
	docker compose logs -f api

##@ Testing & Debugging
test-debug-help: ## Show test debugging commands reference
	python ./run_test_debug.py

test-run: ## Run test debugging script
	python ./run_test_debug.py

test-geofence: ## Run only geofence/location analyzer tests
	cd .. && PYTHONPATH=$$PWD/shared-package/src:$$PYTHONPATH ./.venv/bin/python -m pytest -m geofence -v

##@ Development Setup
install-shared: ## Install/update the shared package
	./microservices.sh install-shared

setup: ## Initial project setup (build, start, migrate)
	@echo "Setting up VTrack project..."
	$(MAKE) build
	$(MAKE) up
	@echo "Waiting for services to start..."
	@sleep 5
	$(MAKE) migrate
	@echo "Setup complete! Run 'make services-status' to verify"

clean: services-clean ## Full cleanup (alias for services-clean)

##@ Quick Actions
start: services-start ## Quick start (alias for services-start)

stop: services-stop ## Quick stop (alias for services-stop)

restart: services-restart ## Quick restart (alias for services-restart)

status: services-status ## Quick status (alias for services-status)
