## VTrack Development Makefile
# Comprehensive development, testing, and operations commands
# All scripts are in the scripts/ directory

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
	./scripts/microservices.sh start

services-stop: ## Stop all microservices
	./scripts/microservices.sh stop

services-restart: ## Restart all microservices
	./scripts/microservices.sh restart

services-status: ## Show status of all services
	./scripts/microservices.sh status

services-health: ## Check health of all services
	./scripts/microservices.sh health

services-logs: ## Show logs for all services (Ctrl+C to exit)
	./scripts/microservices.sh logs

api-logs: ## Show logs for API service only
	./scripts/microservices.sh logs api

alert-logs: ## Show logs for alert processor
	./scripts/microservices.sh logs alert-processor

services-build: ## Build all microservice images
	./scripts/microservices.sh build

services-rebuild: ## Clean rebuild all microservice images
	./scripts/microservices.sh rebuild

services-clean: ## Remove all containers and volumes (DESTRUCTIVE)
	./scripts/microservices.sh clean

##@ Database & Migrations
migrate: ## Run database migrations (upgrade to head)
	./scripts/migrate.sh upgrade

migrate-run: ## Run alembic upgrade head inside api container
	docker compose exec api alembic upgrade head

migrate-current: ## Show current migration version
	./scripts/migrate.sh current

migrate-history: ## Show migration history
	./scripts/migrate.sh history

migrate-status: ## Show detailed migration status
	./scripts/migrate.sh status

migrate-create: ## Create new migration (usage: make migrate-create m="description")
	@if [ -z "$(m)" ]; then \
		echo "Please provide a message: make migrate-create m=\"Your message\""; exit 1; \
	fi
	./scripts/migrate.sh create "$(m)"

migrate-downgrade: ## Rollback one migration (DESTRUCTIVE)
	./scripts/migrate.sh downgrade

migrate-backup: ## Backup database before migration
	./scripts/migrate.sh backup

revision: migrate-create ## Alias for migrate-create

current: migrate-current ## Alias for migrate-current

db-shell: ## Open psql shell to the database
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}

##@ Monitoring & Queue Management
redis-monitor: ## Monitor Redis queues in real-time
	python ./scripts/redis_monitor.py

queue-stats: ## Show Redis queue statistics
	./scripts/microservices.sh queue-stats

logs: ## Follow API container logs
	docker compose logs -f api

##@ Testing & Debugging
test-debug-help: ## Show test debugging commands reference
	python ./scripts/run_test_debug.py

test-run: ## Run test debugging script
	python ./scripts/run_test_debug.py

##@ Development Setup
install-shared: ## Install/update the shared package
	./scripts/microservices.sh install-shared

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
