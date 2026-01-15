.PHONY: help build up down restart logs shell test clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Build the Docker image
	docker-compose build

up: ## Start the container in background
	docker-compose up -d

down: ## Stop and remove containers
	docker-compose down

restart: down up ## Restart the container

logs: ## View container logs
	docker-compose logs -f gemini-webapi

shell: ## Open a shell in the running container
	docker-compose exec gemini-webapi bash

test: ## Run all tests in Docker
	docker-compose --profile test up test --abort-on-container-exit

test-interactive: ## Run tests interactively
	docker-compose exec gemini-webapi python -m pytest tests/ -v

dev: ## Start development environment
	docker-compose -f docker-compose.dev.yml run --rm gemini-webapi-dev

clean: ## Clean up Docker resources
	docker-compose down -v
	docker system prune -f

rebuild: clean build up ## Clean rebuild and start

.DEFAULT_GOAL := help
