.PHONY: help install install-check install-embed lock schemas lint format format-check typecheck test test-integration check migrate migrate-down migration-check db-users load-corpus index-build index-check lexical-index-a lexical-index activate-docs validate-probe canonicalize-probe up down ps

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
	@echo "make lexical-index ACTOR=<id>            (re)build the PRODUCTION lexical index chunk_lexical_tsv (migration 0007, admin DSN)"
	@echo "make index-build ACTOR=<id> [ADMIN_URL=<dsn>] [DEVICE=mps]   lexical index + embeddings + coverage check; run after every ingestion (record 109)"
	@echo "make index-check [ADMIN_URL=<dsn>]        exit 1 if an active chunk is missing from the lexical index or the embeddings"
	@echo "make activate-docs PLAN=<plan.json> ACTOR=<id> ADMIN_URL=<dsn>   activate draft documents all-or-nothing with audited reasons"
	@echo "make check           lint + format-check + typecheck + test + schema drift (CI gate)"
	@echo "make validate-probe DIR=<version_dir> [MODE=draft|frozen] [PAGES=<pages_dir>]"
	@echo "make canonicalize-probe DIR=<draft_dir> [PAGES=<pages_dir>] [CHECK=1]  rewrite draft JSONL to canonical form, then validate"
	@echo "make lock            regenerate requirements.lock from pyproject (uv pip compile, hashed)"
	@echo "make install-embed   install the optional local embedding stack from requirements-embed.lock (ADR-0007)"
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
	# the embed lock is pinned to the main lock's versions (constraints derived from it) so `install-embed` never upgrades a base package
	grep -E '^[A-Za-z0-9_.-]+==' requirements.lock | sed 's/ \\$$//' > .constraints-main.tmp
	uv pip compile pyproject.toml --extra embed --constraint .constraints-main.tmp --python-version 3.11 --generate-hashes -o requirements-embed.lock
	# Linux image locks (M3-12): CPU-only PyTorch index, one per architecture, same constraints
	for arch in aarch64 x86_64; do uv pip compile pyproject.toml --extra embed --constraint .constraints-main.tmp --python-version 3.11 --python-platform $$arch-manylinux_2_28 --extra-index-url https://download.pytorch.org/whl/cpu --index-strategy unsafe-best-match --generate-hashes -o requirements-embed-linux-$$arch.lock; done
	rm -f .constraints-main.tmp

install-embed:
	# optional local inference stack (ADR-0007): PyTorch + sentence-transformers, hashed, on top of `make install`
	$(PY) -m pip install --no-build-isolation --require-hashes -r requirements-embed.lock

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

lexical-index:
	$(PY) -m medops.retrieval.production build-lexical --built-by $(ACTOR)

# after every ingestion / activation: rebuild the lexical index, fill the embedding gaps, then verify coverage (record 109)
index-build:
	$(PY) -m medops.retrieval.production build-lexical --built-by $(ACTOR) $(if $(ADMIN_URL),--admin-url $(ADMIN_URL),)
	$(PY) -m medops.retrieval.production build-embeddings --built-by $(ACTOR) --device $(or $(DEVICE),cpu) $(if $(ADMIN_URL),--admin-url $(ADMIN_URL),)
	$(PY) -m medops.retrieval.production check-indexes $(if $(ADMIN_URL),--admin-url $(ADMIN_URL),)

index-check:
	$(PY) -m medops.retrieval.production check-indexes $(if $(ADMIN_URL),--admin-url $(ADMIN_URL),)

activate-docs:
	$(PY) -m medops.ingestion.activate --plan $(PLAN) --actor $(ACTOR) --admin-url $(ADMIN_URL)

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
