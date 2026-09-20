"""M1-11: publishing a new version archives the old one, activates the new one, writes audit rows and
outbox events in ONE transaction; the outbox is append-only, admin-only and consumed exactly once per
consumer; and an archived version stops being evidence before any index consumer runs.

Own temporary database: the seeds leave active documents behind (non-draft documents cannot be deleted)."""

from __future__ import annotations

import hashlib
import random
import string
from collections.abc import Iterator
from datetime import date

import psycopg
import pytest
from psycopg import errors

from medops.ingestion import outbox
from medops.ingestion.activate import ActivationRefused, activate_document, publish_version
from medops.ingestion.pipeline import DocumentSpec, ingest_document
from medops.retrieval.lexical import index_consumer
from medops.retrieval.lexical import pg_simple_fts as a
from medops.retrieval.lexical.boundary import run_lexical_search
from tests.integration.lexical_adapter_suite import make_database, txn
from tests.integration.pdf_factory import make_pdf

pytest.importorskip("jieba")
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1  # noqa: E402

TOKENIZER = JiebaTokenizerV1()
V1_TEXT = "Alpha label version one {tag}. Adults: 500 mg orally twice daily for seven days. "
V2_TEXT = "Alpha label version two {tag}. Adults: 250 mg orally once daily for five days. "


def _spec(data: bytes, key: str, version: str) -> DocumentSpec:
    return DocumentSpec(
        document_key=key,
        title="Synthetic label",
        doc_type="label",
        owner_dept="MA",
        language="en",
        version_label=version,
        source_hash=hashlib.sha256(data).hexdigest(),
        byte_size=len(data),
        source_url="https://example.invalid/x.pdf",
        publisher="Synthetic",
        retrieved_at=date(2026, 9, 20),
        terms_url="https://example.invalid/terms",
        license_name="CC BY 4.0 (synthetic)",
        attribution_text="Synthetic",
    )


def _ingest(conn, tmp_path, key, version, text, *, supersedes=None):
    data = make_pdf([text])
    path = tmp_path / f"{key}.pdf"
    path.write_bytes(data)
    return ingest_document(conn, _spec(data, key, version), path, actor="ingest-01", supersedes=supersedes)


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


@pytest.fixture
def family(db, tmp_path):
    """v1 active (effective 2026-01-01) and v2 draft superseding it; unique keys per test."""
    tag = "".join(random.choices(string.ascii_lowercase, k=8))  # a plain word present in every chunk
    with psycopg.connect(db["users"]["admin"]) as admin:
        v1 = _ingest(admin, tmp_path, f"lbl-{tag}-v1", "2026-01", V1_TEXT.format(tag=tag) * 8)
        activate_document(admin, f"lbl-{tag}-v1", date(2026, 1, 1), actor="reviewer-01", reason="first version")
        v2 = _ingest(admin, tmp_path, f"lbl-{tag}-v2", "2026-09", V2_TEXT.format(tag=tag) * 8, supersedes=v1.doc_id)
        admin.commit()
    return {"tag": tag, "v1": v1, "v2": v2, "k1": f"lbl-{tag}-v1", "k2": f"lbl-{tag}-v2"}


def test_outbox_tables_are_admin_only_and_append_only(db, family):
    for kind in ("app", "readonly"):
        with psycopg.connect(db["users"][kind]) as conn:
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute("select count(*) from outbox_events").fetchone()
            conn.rollback()
    with psycopg.connect(db["users"]["admin"]) as admin:
        rows = admin.execute(
            "select event_id, event_type, payload from outbox_events where family_id = %s order by event_id",
            (admin.execute("select family_id from documents where doc_id = %s", (family["v1"].doc_id,)).fetchone()[0],),
        ).fetchall()
        assert [r[1] for r in rows] == ["document_activated"] and rows[0][2]["document_key"] == family["k1"]
        eid = rows[0][0]
        with pytest.raises(errors.RestrictViolation):
            admin.execute("update outbox_events set payload = '{}'::jsonb where event_id = %s", (eid,))
        admin.rollback()
        with pytest.raises(errors.InsufficientPrivilege):  # the admin role has no DELETE grant at all
            admin.execute("delete from outbox_events where event_id = %s", (eid,))
        admin.rollback()
    with psycopg.connect(db["owner"]) as owner:  # even the table owner is stopped by the append-only trigger
        with pytest.raises(errors.RestrictViolation):
            owner.execute("delete from outbox_events where event_id = %s", (eid,))
        owner.rollback()
    with psycopg.connect(db["users"]["admin"]) as admin:
        admin.execute("update outbox_events set attempts = attempts + 1, last_error = 'x' where event_id = %s", (eid,))
        admin.rollback()


def test_publish_archives_old_and_activates_new_in_one_transaction_with_events(db, family):
    with psycopg.connect(db["users"]["admin"]) as admin:
        pub = publish_version(admin, family["k2"], date(2026, 9, 1), actor="reviewer-01", reason="new revision")
        admin.commit()
        rows = {
            r[0]: r[1:]
            for r in admin.execute(
                "select document_key, status::text, effective_from, effective_to from documents where document_key in (%s, %s)",
                (family["k1"], family["k2"]),
            )
        }
        assert rows[family["k1"]] == ("archived", date(2026, 1, 1), date(2026, 9, 1))
        assert rows[family["k2"]] == ("active", date(2026, 9, 1), None)
        audits = admin.execute(
            "select d.document_key, x.from_status::text, x.to_status::text, x.actor, x.reason from doc_audit x join documents d using (doc_id) "
            "where d.document_key in (%s, %s) and x.to_status is not null order by x.id",
            (family["k1"], family["k2"]),
        ).fetchall()
        assert (family["k1"], "active", "archived", "reviewer-01", "new revision") in audits
        assert (family["k2"], "draft", "active", "reviewer-01", "new revision") in audits
        events = admin.execute(
            "select event_type, payload from outbox_events where event_id = any(%s) order by event_id",
            (list(pub.events),),
        ).fetchall()
        assert [e[0] for e in events] == ["document_archived", "document_activated"]
        assert events[0][1]["effective_to"] == "2026-09-01" and events[0][1]["superseded_by"] == pub.new_doc_id
        assert events[1][1]["supersedes"] == pub.archived_doc_id and events[1][1]["acl_depts"] == ["MA"]
        # the family has exactly one active version and a second publish of the same draft is refused
        assert admin.execute(
            "select count(*) from documents where family_id = (select family_id from documents where doc_id = %s) and status = 'active'",
            (family["v1"].doc_id,),
        ).fetchone() == (1,)
        with pytest.raises(ActivationRefused, match="only a draft"):
            publish_version(admin, family["k2"], date(2026, 9, 2), actor="reviewer-01", reason="again")


def test_publish_refusals_leave_everything_unchanged(db, family, tmp_path, monkeypatch):
    with psycopg.connect(db["users"]["admin"]) as admin:
        with pytest.raises(ActivationRefused, match="must be after"):
            publish_version(admin, family["k2"], date(2026, 1, 1), actor="reviewer-01", reason="r")
        with pytest.raises(ActivationRefused, match="only a draft"):
            publish_version(admin, family["k1"], date(2026, 9, 1), actor="reviewer-01", reason="r")
        lone = _ingest(admin, tmp_path, f"lone-{family['tag']}", "2026-01", "Standalone draft without a chain. " * 20)
        with pytest.raises(ActivationRefused, match="no supersedes link"):
            publish_version(admin, f"lone-{family['tag']}", date(2026, 9, 1), actor="reviewer-01", reason="r")
        assert lone.status == "ingested"
        # a failure after the two status updates rolls back both of them and the audit rows
        from medops.ingestion import activate as act_mod

        def boom(*args, **kwargs):
            raise RuntimeError("outbox unavailable")

        monkeypatch.setattr(act_mod, "_emit_status_event", boom)
        with pytest.raises(RuntimeError):
            publish_version(admin, family["k2"], date(2026, 9, 1), actor="reviewer-01", reason="r")
        admin.rollback()
        statuses = dict(
            admin.execute(
                "select document_key, status::text from documents where document_key in (%s, %s)",
                (family["k1"], family["k2"]),
            ).fetchall()
        )
        assert statuses == {family["k1"]: "active", family["k2"]: "draft"}
        assert admin.execute(
            "select count(*) from doc_audit x join documents d using (doc_id) where d.document_key = %s and x.to_status = 'archived'",
            (family["k1"],),
        ).fetchone() == (0,)


def test_archived_version_is_not_evidence_before_the_index_consumer_runs(db, family):
    """Index latency must not make the old version valid evidence (baseline M1-11)."""
    owner, admin_dsn, app_dsn = db["owner"], db["users"]["admin"], db["users"]["app"]
    with psycopg.connect(owner) as o:
        a.install(o)
        o.commit()
    with psycopg.connect(admin_dsn) as admin:
        a.build_index(admin, TOKENIZER, built_by="test")  # v1 chunks indexed (v2 draft chunks too)
        admin.commit()
    expected = a.configured_versions(TOKENIZER)
    with txn(app_dsn, "MA") as conn:
        before = run_lexical_search(
            a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=date(2026, 9, 20)), family["tag"], 20, expected=expected
        )
    v1_chunks = {
        str(r[0])
        for r in psycopg.connect(admin_dsn).execute(
            "select chunk_id from chunks where doc_id = %s", (family["v1"].doc_id,)
        )
    }
    v2_chunks = {
        str(r[0])
        for r in psycopg.connect(admin_dsn).execute(
            "select chunk_id from chunks where doc_id = %s", (family["v2"].doc_id,)
        )
    }
    assert {c.chunk_id for c in before.candidates} == v1_chunks  # only the active v1 is visible
    with psycopg.connect(admin_dsn) as admin:
        publish_version(admin, family["k2"], date(2026, 9, 1), actor="reviewer-01", reason="new revision")
        admin.commit()
    with txn(app_dsn, "MA") as conn:
        after_publish = run_lexical_search(
            a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=date(2026, 9, 20)), family["tag"], 20, expected=expected
        )
    # index rows of v1 still exist, yet the archived version is filtered out inside the query; v2 already indexed at build time
    assert {c.chunk_id for c in after_publish.candidates} == v2_chunks
    with psycopg.connect(admin_dsn) as admin:
        assert (
            admin.execute(
                f"select count(*) from {a.INDEX_TABLE} i join chunks c using (chunk_id) where c.doc_id = %s",
                (family["v1"].doc_id,),
            ).fetchone()[0]
            > 0
        )
        acked = index_consumer.consume(admin, [index_consumer.tsvector_target(a.INDEX_TABLE, TOKENIZER)])
        admin.commit()
        assert len(acked) >= 2
        assert admin.execute(
            f"select count(*) from {a.INDEX_TABLE} i join chunks c using (chunk_id) where c.doc_id = %s",
            (family["v1"].doc_id,),
        ).fetchone() == (0,)
        assert admin.execute(
            f"select count(*) from {a.INDEX_TABLE} i join chunks c using (chunk_id) where c.doc_id = %s",
            (family["v2"].doc_id,),
        ).fetchone() == (len(v2_chunks),)
        # redelivery is harmless: nothing left to claim, and re-running keeps the same rows
        assert index_consumer.consume(admin, [index_consumer.tsvector_target(a.INDEX_TABLE, TOKENIZER)]) == []
        admin.commit()
    with txn(app_dsn, "MA") as conn:
        final = run_lexical_search(
            a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=date(2026, 9, 20)), family["tag"], 20, expected=expected
        )
    assert {c.chunk_id for c in final.candidates} == v2_chunks


def test_two_consumers_claim_disjoint_events_and_each_event_is_acked_once(db, family):
    with psycopg.connect(db["users"]["admin"]) as admin:
        publish_version(admin, family["k2"], date(2026, 9, 1), actor="reviewer-01", reason="r")
        admin.commit()
    consumer = f"test-{family['tag']}"
    c1, c2 = psycopg.connect(db["users"]["admin"]), psycopg.connect(db["users"]["admin"])
    try:
        with c1.transaction():
            first = outbox.claim(c1, consumer, limit=1)
            with c2.transaction():
                second = outbox.claim(c2, consumer, limit=50)
                assert first and second and {e.event_id for e in first}.isdisjoint({e.event_id for e in second})
                for e in second:
                    outbox.ack(c2, consumer, e.event_id)
            for e in first:
                outbox.ack(c1, consumer, e.event_id)
        remaining = outbox.claim(c1, consumer)
        c1.rollback()
        assert remaining == []
        with pytest.raises(errors.UniqueViolation):
            outbox.ack(c1, consumer, first[0].event_id)
        c1.rollback()
        assert outbox.mark_published_when_complete(c1, [consumer]) >= 1
        c1.commit()
    finally:
        c1.close()
        c2.close()
