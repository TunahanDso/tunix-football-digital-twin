PYTHON ?= python

.PHONY: install test lint format api infra-up infra-down

install:
	$(PYTHON) -m pip install -e '.[dev,modeling]'

test:
	pytest -q

lint:
	ruff check .
	mypy src/tunix_football

format:
	ruff format .
	ruff check . --fix

api:
	uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

infra-up:
	docker compose up -d

infra-down:
	docker compose down
