.PHONY: help run migrate lint test test-integration test-all deploy

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-16s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run: ## Start the development server (with auto-reload)
	@./scripts/run.sh

migrate: ## Run database migrations
	@./scripts/migrate.sh

lint: ## Run linting checks (ruff)
	@./scripts/lint.sh

test: ## Run unit tests + incremental coverage check (mirrors CI)
	@./scripts/test.sh

test-integration: ## Run integration tests only (requires local middleware)
	@uv run --extra dev pytest tests/integration -q

test-all: ## Run unit tests + integration tests (full local suite)
	@uv run --extra dev pytest tests/unit tests/integration -q \
		--cov=src \
		--cov-report=term-missing

deploy: ## Deploy the application
	@./scripts/deploy.sh
