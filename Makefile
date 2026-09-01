# Syncore developer commands. On Windows, either use `make` (via Git Bash / WSL)
# or run the equivalent commands shown in README.md.

PY ?= python
VENV ?= .venv

.PHONY: help setup dev api web test lint format migrate seed slice docker-up docker-down clean

help:
	@echo "Syncore make targets:"
	@echo "  setup      Create venv and install the package (dev extras)"
	@echo "  api        Run the FastAPI server (http://127.0.0.1:8000)"
	@echo "  web        Run the Next.js dev server (http://127.0.0.1:3000)"
	@echo "  slice      Run the end-to-end vertical slice from the CLI"
	@echo "  test       Run the test suite"
	@echo "  lint       Ruff lint"
	@echo "  format     Ruff format"
	@echo "  migrate    Create database tables"
	@echo "  seed       Seed demo data"
	@echo "  docker-up  docker compose up --build"
	@echo "  docker-down docker compose down"

setup:
	$(PY) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e ".[dev]"

api:
	$(VENV)/bin/uvicorn syncore.api.app:app --reload --host 127.0.0.1 --port 8000

web:
	cd web && npm install && npm run dev

slice:
	$(VENV)/bin/python -m syncore.scripts.vertical_slice

test:
	$(VENV)/bin/python -m pytest -p no:warnings

lint:
	$(VENV)/bin/ruff check src tests

format:
	$(VENV)/bin/ruff format src tests

migrate:
	$(VENV)/bin/python -m syncore.scripts.manage migrate

seed:
	$(VENV)/bin/python -m syncore.scripts.manage seed

docker-up:
	docker compose up --build

docker-down:
	docker compose down

clean:
	rm -rf $(VENV) .pytest_cache **/__pycache__ syncore.db
