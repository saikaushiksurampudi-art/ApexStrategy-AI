# ApexStrategy AI -- common development tasks.
.DEFAULT_GOAL := help
SHELL := /bin/bash
PY := backend/.venv/bin/python
PIP := backend/.venv/bin/pip

.PHONY: help setup install-backend install-frontend ingest train test test-cov \
        test-frontend test-all lint dev-backend dev-frontend build docker-build \
        docker-up docker-down migrate clean bootstrap

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

setup: install-backend install-frontend ## Install all dependencies

install-backend: ## Create the venv and install Python dependencies
	python3 -m venv backend/.venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements-dev.txt

install-frontend: ## Install Node dependencies
	cd frontend && npm install

bootstrap: ingest train ## Load historical data, then train the model
	@echo "Bootstrap complete. Start the API with 'make dev-backend'."

ingest: ## Download historical F1 data (2021-2025) into the database
	cd backend && .venv/bin/python -m scripts.ingest

train: ## Train the podium model and print its evaluation
	cd backend && .venv/bin/python -m scripts.train_model

test: ## Run the backend test suite
	cd backend && .venv/bin/python -m pytest

test-cov: ## Run the backend tests with a coverage report
	cd backend && .venv/bin/python -m pytest --cov=app --cov-report=term-missing

test-frontend: ## Type-check and unit-test the frontend
	cd frontend && npm run lint && npm test

test-all: test test-frontend ## Run every test suite

lint: ## Lint the backend
	cd backend && .venv/bin/ruff check app scripts tests

migrate: ## Apply database migrations
	cd backend && .venv/bin/alembic upgrade head

dev-backend: ## Run the API with hot reload on :8000
	cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

dev-frontend: ## Run the Vite dev server on :5173
	cd frontend && npm run dev

build: ## Build the production frontend bundle
	cd frontend && npm run build

docker-build: ## Build the production container image
	docker build -t apexstrategy:local .

docker-up: ## Start PostgreSQL and the app with docker compose
	docker compose up --build

docker-down: ## Stop the compose stack
	docker compose down

clean: ## Remove caches, build output and local artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .pytest_cache -prune -exec rm -rf {} +
	rm -rf frontend/dist backend/.coverage backend/htmlcov
