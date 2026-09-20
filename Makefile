.PHONY: help install install-check lock schemas lint format format-check typecheck test test-integration check migrate migrate-down migration-check db-users load-corpus lexical-index-a validate-probe canonicalize-probe up down ps

# venv lives in a NON-dot directory on purpose: ~/Documents is an iCloud Drive domain that marks every file
# inside dot-directories as hidden, and CPython >= 3.11.16 skips hidden .pth files, which silently breaks
# editable installs placed in .venv/. See docs/reviews/2026-09-10-implementation-03-validator-hardening.md.
PY ?= venv/bin/python
# Installer pin: the only tool that is not in requirements.lock. Bump deliberately together with the lock.
PIP_VERSION ?= 26.2.1

help:
	@echo "make install         create venv/ (python3.11) and install with dev extras"
	@echo "make lint            ruff check src tests migrations"
	@echo "make format          ruff format src tests migrations"
	@echo "make format-check    ruff format --check src tests migrations (part of make check)"
	@echo "make typecheck       mypy src"
	@echo "make test            pytest (unit + integration; integration skips with a reason when PostgreSQL is down)"
	@echo "make test-integration pytest tests/integration only (needs make up or MEDOPS_TEST_ADMIN_URL)"
	@echo "make migrate | migrate-down | migration-check   alembic upgrade head | downgrade -1 | single head + round-trip tests"
	@echo "make db-users        create/rotate LOGIN users for the 0002 group roles (DB_*_PASSWORD from .env)"
	@echo "make load-corpus CORPUS=<corpus.json> SOURCES=<dir> PAGES=<dir> ACTOR=<id> [ARGS=...]   ingest documents into the fact plane"
	@echo "make lexical-index-a ACTOR=<id>          install and (re)build the DEC-001 candidate A lexical index (admin DSN)"
	@echo "make check           lint + format-check + typecheck + test + schema drift (CI gate)"
	@echo "make validate-probe DIR=<version_dir> [MODE=draft|frozen] [PAGES=<pages_dir>]"
	@echo "make canonicalize-probe DIR=<draft_dir> [PAGES=<pages_dir>] [CHECK=1]  rewrite draft JSONL to canonical form, then validate"
	@echo "make lock            regenerate requirements.lock from pyproject (uv pip compile, hashed)"
	@echo "make schemas         export API/MCP JSON Schemas and openapi.json to schemas/ (check runs the drift test)"
	@echo "make up | down | ps  local PostgreSQL/pgvector + Redis via docker compose (needs .env)"

install:
	python3.11 -m venv venv
	$(PY) -m pip install "pip==$(PIP_VERSION)"
	# 1) build backend first (pinned + hashed) so source-only packages in the lock (jieba) build with it
	$(PY) -m pip install --require-hashes -r requirements-build.lock
	# 2) locked dependencies without build isolation: no hidden re-resolution of build requirements
	$(PY) -m pip install --no-build-isolation -r requirements.lock
	# 3) the project itself, no deps
	$(PY) -m pip install --no-build-isolation --no-deps -e .
	$(PY) -m pip check
	$(MAKE) install-check

lock:
	uv pip compile pyproject.toml --extra dev --python-version 3.11 --generate-hashes -o requirements.lock
	uv pip compile requirements-build.in --python-version 3.11 --generate-hashes -o requirements-build.lock

install-check:
	@cd /tmp && $(CURDIR)/$(PY) -c "import medops.evals.probe.validator" && echo "install-check: medops importable outside the repo"

lint:
	$(PY) -m ruff check src tests migrations

format:
	$(PY) -m ruff format src tests migrations

format-check:
	$(PY) -m ruff format --check src tests migrations

typecheck:
	$(PY) -m mypy

test:
	$(PY) -m pytest -q

test-integration:
	$(PY) -m pytest -q tests/integration

migrate:
	$(PY) -m alembic upgrade head

migrate-down:
	$(PY) -m alembic downgrade -1

db-users:
	$(PY) -m medops.infrastructure.db.login_users

load-corpus:
	$(PY) -m medops.ingestion.load --corpus $(CORPUS) --sources-dir $(SOURCES) $(if $(PAGES),--pages-dir $(PAGES),) --actor $(ACTOR) $(ARGS)

lexical-index-a:
	$(PY) -m medops.retrieval.lexical.pg_simple_fts install
	$(PY) -m medops.retrieval.lexical.pg_simple_fts build --built-by $(ACTOR)

migration-check:
	@test "$$($(PY) -m alembic heads | wc -l | tr -d ' ')" = "1" && echo "migration-check: single head"
	$(PY) -m pytest -q tests/integration/test_migrations.py -k "round_trip or single_head"

check: install-check lint format-check typecheck test
	$(PY) -m medops.contracts_export --out schemas --check

schemas:
	$(PY) -m medops.contracts_export --out schemas

MODE ?= draft
validate-probe:
	$(PY) -m medops.evals.probe $(DIR) --mode $(MODE) $(if $(PAGES),--pages $(PAGES),)

canonicalize-probe:
	$(PY) -m medops.evals.probe.canonicalize $(DIR) $(if $(PAGES),--pages $(PAGES),) $(if $(CHECK),--check,)

up:
	docker compose --env-file .env up -d --wait

down:
	docker compose --env-file .env down

ps:
	docker compose --env-file .env ps
