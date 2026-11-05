SHELL := /bin/sh
.DEFAULT_GOAL := help
UV ?= uv
UV_RUN := $(UV) run --locked
COMPOSE := docker compose --env-file .env

.PHONY: help setup dev test lint typecheck migrate smoke down build logs status clean seed
help:
	@echo 'EARTHMIND M04: setup dev down test lint typecheck migrate seed smoke logs status clean build'

setup:
	sh scripts/bootstrap.sh
	$(UV) sync --all-packages --group dev --locked
	npm ci
	$(UV_RUN) pre-commit install

dev:
	$(UV_RUN) python scripts/check_architecture.py --host-only
	$(COMPOSE) up --build --detach --wait --wait-timeout 240
	$(UV_RUN) python scripts/check_architecture.py
	$(MAKE) seed
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

seed:
	$(COMPOSE) run --rm migrate python -m earthmind_api.seed

smoke:
	$(UV_RUN) python scripts/smoke.py
	$(UV_RUN) python scripts/geospatial_smoke.py
	$(UV_RUN) python scripts/check_cesium_assets.py

down:
	$(COMPOSE) down --remove-orphans

logs:
	$(COMPOSE) logs --tail=100

status:
	$(COMPOSE) ps --all

clean:
	$(UV_RUN) python scripts/clean.py

.PHONY: import-dubai smoke-real
import-dubai:
	$(UV_RUN) python scripts/import_dubai_osm.py download
	$(UV_RUN) python scripts/import_dubai_osm.py convert
	$(UV_RUN) python scripts/import_dubai_osm.py import
	$(UV_RUN) python scripts/build_osm_context.py --source data/dubai-osm/recovery-v1/source.osm.xml --output data/dubai-osm/recovery-v1/context
	$(COMPOSE) up --detach --no-deps --force-recreate --wait --wait-timeout 120 web

smoke-real:
	$(UV_RUN) python scripts/run_real_network_smoke.py
