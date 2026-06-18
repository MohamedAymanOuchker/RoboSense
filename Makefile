# RoboSense developer commands.
# Windows users without `make`: run the underlying `docker compose ...` commands
# shown in each target directly (see README "Local development").

COMPOSE := docker compose

.PHONY: help up down logs ps seed test lint fmt rebuild clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

up: ## Build and start the full stack (db + backend) in the background
	@test -f .env || cp .env.example .env
	$(COMPOSE) up -d --build
	@echo ""
	@echo "RoboSense is up:"
	@echo "  API      -> http://localhost:8000"
	@echo "  Docs     -> http://localhost:8000/docs"
	@echo "  Health   -> http://localhost:8000/api/health"

down: ## Stop and remove the stack (keeps the database volume)
	$(COMPOSE) down

logs: ## Follow logs from all services
	$(COMPOSE) logs -f

ps: ## Show running services
	$(COMPOSE) ps

seed: ## Populate the database with fake telemetry (added in Milestone 3)
	$(COMPOSE) exec backend python -m app.seed

test: ## Run the backend test suite inside the backend container
	$(COMPOSE) exec backend pytest -q

lint: ## Run ruff lint inside the backend container
	$(COMPOSE) exec backend ruff check .

fmt: ## Auto-format backend code with ruff
	$(COMPOSE) exec backend ruff format .

rebuild: ## Rebuild images from scratch (no cache)
	$(COMPOSE) build --no-cache

clean: ## Stop the stack and delete the database volume (destroys all data)
	$(COMPOSE) down -v
