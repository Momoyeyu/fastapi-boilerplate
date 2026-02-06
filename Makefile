.PHONY: help run migrate lint test deploy

# Default target
.DEFAULT_GOAL := help

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ {printf "  %-12s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

run: ## Start the development server (with auto-reload)
	@./scripts/run.sh

migrate: ## Run database migrations
	@./scripts/migrate.sh

lint: ## Run linting checks (ruff). Use fix=1 to auto-fix
	@./scripts/lint.sh $(if $(fix),--fix)

test: ## Run all tests (unit + integration)
	@./scripts/test.sh

deploy: ## Deploy the application
	@./scripts/deploy.sh
