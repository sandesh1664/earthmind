SHELL := /bin/sh
.DEFAULT_GOAL := help
UV ?= uv
UV_RUN := $(UV) run --locked
COMPOSE := docker compose --env-file .env

.PHONY: help setup dev test lint typecheck migrate smoke down build logs status clean
help:
	@echo 'EARTHMIND M01: setup dev down test lint typecheck migrate smoke logs status clean build'

setup:
	sh scripts/bootstrap.sh
	$(UV) sync --all-packages --group dev --locked
	npm ci
	$(UV_RUN) pre-commit install

dev:
	$(UV_RUN) python scripts/check_architecture.py --host-only
	$(COMPOSE) up --build --detach --wait --wait-timeout 240
	$(UV_RUN) python scripts/check_architecture.py
	$(MAKE) smoke

test:
	$(UV_RUN) pytest
	npm run test

lint:
	$(UV) lock --check
	$(UV_RUN) python packages/contracts/generate_types.py --check
	$(UV_RUN) ruff check .
	$(UV_RUN) ruff format --check .
	npm run lint
	$(MAKE) typecheck

typecheck:
	$(UV_RUN) mypy
	npm run typecheck

build:
	npm run build

migrate:
	$(COMPOSE) run --rm migrate

smoke:
	$(UV_RUN) python scripts/smoke.py

down:
	$(COMPOSE) down --remove-orphans

logs:
	$(COMPOSE) logs --tail=100

status:
	$(COMPOSE) ps --all

clean:
	$(UV_RUN) python scripts/clean.py
