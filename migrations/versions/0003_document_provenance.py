"""Provenance and licence fields on documents; extraction quality counters on ingestion jobs (M1-09/10, M5-01).

`documents.document_key` is the stable external key used by the probe corpus.json and by loaders
(unique when present). Source URL, publisher, retrieval date, licence name, terms URL and attribution
text record where a version came from and under which terms it may be shown (baseline 5.1 "记录来源和
版本", ADR-0003). `ingestion_jobs.extractor_warnings` / `empty_pages` keep the numbers that decide
parse_quality auditable.

Revision ID: 0003
Revises: 0002
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

UP = [
    "alter table documents add column document_key text check (document_key ~ '^[a-z0-9][a-z0-9-]{2,63}$')",
    "create unique index documents_document_key_unique on documents (document_key) where document_key is not null",
    "alter table documents add column source_url text check (source_url ~ '^https?://')",
    "alter table documents add column publisher text check (length(publisher) > 0)",
    "alter table documents add column retrieved_at date",
    "alter table documents add column license_name text check (length(license_name) > 0)",
    "alter table documents add column terms_url text check (terms_url ~ '^https?://')",
    "alter table documents add column attribution_text text",
    "comment on column documents.document_key is 'Stable external key (probe corpus.json document_key); unique when set.'",
    "alter table ingestion_jobs add column extractor_warnings integer check (extractor_warnings >= 0)",
    "alter table ingestion_jobs add column empty_pages integer check (empty_pages >= 0)",
]

DOWN = [
    "alter table ingestion_jobs drop column if exists empty_pages",
    "alter table ingestion_jobs drop column if exists extractor_warnings",
    "alter table documents drop column if exists attribution_text",
    "alter table documents drop column if exists terms_url",
    "alter table documents drop column if exists license_name",
    "alter table documents drop column if exists retrieved_at",
    "alter table documents drop column if exists publisher",
    "alter table documents drop column if exists source_url",
    "drop index if exists documents_document_key_unique",
    "alter table documents drop column if exists document_key",
]


def upgrade() -> None:
    for statement in UP:
        op.execute(statement)


def downgrade() -> None:
    for statement in DOWN:
        op.execute(statement)
