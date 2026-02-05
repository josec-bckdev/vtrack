## Makefile - common development and migration tasks
# Targets are written for convenience in local development and CI.

.PHONY: help build up down rebuild migrate migrate-run revision current logs db-shell

help:
	@echo "Make targets:"
	@echo "  build          - Build the API Docker image (no cache)"
	@echo "  up             - Start services in background (docker compose up -d)"
	@echo "  down           - Stop and remove containers"
	@echo "  rebuild        - Rebuild API image and start"
	@echo "  migrate        - Run migration job (docker compose run --rm migrate)"
	@echo "  migrate-run    - Run alembic upgrade head inside api container"
	@echo "  revision m=MSG - Create an alembic revision with message MSG"
	@echo "  current        - Show current alembic head"
	@echo "  logs           - Follow API container logs"
	@echo "  db-shell       - Open psql shell to the postgres service"

build:
	docker compose build api --no-cache

up:
	docker compose up -d

down:
	docker compose down

rebuild: down build up

# Run the migrate service which executes `alembic upgrade head` and exits
migrate:
	docker compose run --rm migrate

# Run alembic upgrade head inside the running api container
migrate-run:
	docker compose exec api alembic upgrade head

# Create a new revision. Usage: make revision m="Add column"
revision:
	@if [ -z "$(m)" ]; then \
		echo "Please provide a message: make revision m=\"Your message\""; exit 1; \
	fi
	docker compose exec api alembic revision --autogenerate -m "$(m)"

current:
	docker compose exec api alembic current

logs:
	docker compose logs -f api

# Open a psql shell to the DB (reads credentials from .env)
db-shell:
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}
