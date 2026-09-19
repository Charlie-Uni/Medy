"""Alembic environment (M1-06).

Revisions are written as plain SQL through `op.execute`, so there is no SQLAlchemy metadata and no
autogenerate. The connection URL comes from, in order: the MEDOPS_MIGRATION_URL environment variable
(integration tests point it at a throwaway database), then `Settings.database_admin_url`, then
`Settings.database_url`. The URL is normalised to the psycopg 3 driver. Each revision runs in its own
transaction so a failed revision leaves the database at the previous version.
"""

from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

config = context.config
if config.config_file_name is not None:
    # keep application loggers (e.g. pypdf warning counting) alive when migrations run in-process
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = None


def _psycopg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg://"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    raise ValueError("migration URL must be a postgresql:// DSN")


def database_url() -> str:
    explicit = os.environ.get("MEDOPS_MIGRATION_URL")
    if explicit:
        return _psycopg_url(explicit)
    from medops.core.config import Settings  # imported lazily so `alembic --help` works without a .env

    settings = Settings()
    secret = settings.database_admin_url or settings.database_url
    return _psycopg_url(secret.get_secret_value())


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(), literal_binds=True, dialect_opts={"paramstyle": "named"}, transaction_per_migration=True
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool, future=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
