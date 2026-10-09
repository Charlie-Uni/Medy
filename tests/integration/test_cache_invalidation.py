"""M1-19 on the real fact plane: a cache hit never bypasses the re-check (revocation takes effect at once),
publishing a new version invalidates only the reading departments' entries through the outbox consumer, a
changed version or department is a different key, and candidates computed under one identity are never
served to another. The complete publish/consume/retrieve path also runs through a real isolated Redis namespace.

Own temporary database: the seeds leave active documents behind (non-draft documents cannot be deleted)."""

from __future__ import annotations

import hashlib
import random
import string
from collections.abc import Iterator
from datetime import date

import psycopg
import pytest

from medops.domain import CandidateRef, Dept, SourceRank, UserContext
from medops.infrastructure.cache import RedisCandidateCacheStore
from medops.ingestion.activate import activate_document, publish_version
from medops.ingestion.pipeline import DocumentSpec, ingest_document
from medops.retrieval import cache_consumer
from medops.retrieval.cache import CacheKeyInputs, CandidateCache, InMemoryCandidateCacheStore, fetch_evidence
from medops.retrieval.lexical import index_consumer
from medops.retrieval.lexical import pg_simple_fts as a
from medops.retrieval.lexical.boundary import run_lexical_search
from tests.integration.lexical_adapter_suite import make_database, txn
from tests.integration.pdf_factory import make_pdf

pytest.importorskip("jieba")
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1  # noqa: E402

TOKENIZER = JiebaTokenizerV1()
AS_OF = date(2026, 9, 20)
R1 = hashlib.sha256(b"retrieval-version-1").hexdigest()
R2 = hashlib.sha256(b"retrieval-version-2").hexdigest()
MA = UserContext(user_id="u-ma", dept=Dept.MA, acl_scopes=frozenset({"MA:read"}))
V1_TEXT = "Beta label version one {tag}. Adults: 500 mg orally twice daily for seven days. "
V2_TEXT = "Beta label version two {tag}. Adults: 250 mg orally once daily for five days. "


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


@pytest.fixture(scope="module")
def indexed(db) -> None:
    with psycopg.connect(db["owner"]) as conn:
        a.install(conn)
        conn.commit()


@pytest.fixture
def family(db, indexed, tmp_path):
    """v1 active (since 2026-01-01) and v2 draft superseding it, the index rebuilt so both are present."""
    tag = "".join(random.choices(string.ascii_lowercase, k=8))
    with psycopg.connect(db["users"]["admin"]) as admin:
        v1 = _ingest(admin, tmp_path, f"lbl-{tag}-v1", "2026-01", V1_TEXT.format(tag=tag) * 8)
        activate_document(admin, f"lbl-{tag}-v1", date(2026, 1, 1), actor="reviewer-01", reason="first version")
        v2 = _ingest(admin, tmp_path, f"lbl-{tag}-v2", "2026-09", V2_TEXT.format(tag=tag) * 8, supersedes=v1.doc_id)
        a.build_index(admin, TOKENIZER, built_by="test-admin-01")
        admin.commit()
        chunks = {
            key: {str(r[0]) for r in admin.execute("select chunk_id from chunks where doc_id = %s", (doc.doc_id,))}
            for key, doc in (("v1", v1), ("v2", v2))
        }
    return {"tag": tag, "v1": v1, "v2": v2, "k1": f"lbl-{tag}-v1", "k2": f"lbl-{tag}-v2", "chunks": chunks}


def _compute(conn, tag):
    """The retrieval work the cache saves: candidate A under the transaction's identity."""

    def compute() -> tuple[CandidateRef, ...]:
        retriever = a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=AS_OF)
        hits = run_lexical_search(retriever, tag, 20, expected=retriever.versions)
        return tuple(
            CandidateRef(chunk_id=c.chunk_id, source_ranks=(SourceRank(source="lexical", rank=c.rank),))
            for c in hits.candidates
        )

    return compute


def _inputs(tag, *, user=MA, retrieval_version=R1, policy_version="policy-v1", as_of=AS_OF):
    return CacheKeyInputs.build(
        query=tag, user=user, as_of=as_of, retrieval_version=retrieval_version, policy_version=policy_version
    )


def test_a_hit_is_still_rechecked_so_revocation_takes_effect_before_any_invalidation(db, family):
    cache = CandidateCache(InMemoryCandidateCacheStore())
    tag = family["tag"]
    with txn(db["users"]["app"], "MA") as conn:
        first, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
        assert hit is False and first.evidence and set(first.accepted_ids) <= family["chunks"]["v1"]
        second, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
        assert hit is True and second.accepted_ids == first.accepted_ids
    with psycopg.connect(db["users"]["admin"]) as admin:
        admin.execute("delete from document_acl where doc_id = %s and dept = 'MA'", (family["v1"].doc_id,))
        admin.commit()
    with txn(db["users"]["app"], "MA") as conn:
        revoked, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
    assert hit is True  # the entry is still cached ...
    assert revoked.evidence == () and {r.reason.value for r in revoked.rejected} == {"not_visible"}  # ... and useless
    narrower = MA.model_copy(update={"acl_scopes": frozenset()})
    with txn(db["users"]["app"], "MA") as conn:
        _, hit = fetch_evidence(conn, cache, _inputs(tag, user=narrower), _compute(conn, tag))
    assert hit is False  # a different permission set is a different key


def test_publishing_a_new_version_invalidates_the_readers_departments_through_the_outbox(db, family):
    store = InMemoryCandidateCacheStore()
    cache = CandidateCache(store)
    tag = family["tag"]
    with txn(db["users"]["app"], "MA") as conn:
        before, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
        assert hit is False and set(before.accepted_ids) <= family["chunks"]["v1"] and before.accepted_ids
    with psycopg.connect(db["users"]["admin"]) as admin:
        publish_version(admin, family["k2"], AS_OF.replace(month=9, day=1), actor="reviewer-01", reason="v2")
        admin.commit()
    # Committed but no consumer has run: the hit serves the old candidate list and the re-check empties it.
    with txn(db["users"]["app"], "MA") as conn:
        stale, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
    assert hit is True and stale.evidence == ()
    assert {r.reason.value for r in stale.rejected} == {"status_not_active"}
    ma_before, pv_before = store.get_epoch("MA"), store.get_epoch("PV")
    with psycopg.connect(db["users"]["admin"]) as admin:
        index_consumer.consume(admin, [index_consumer.tsvector_target(a.INDEX_TABLE, TOKENIZER)])
        acked = cache_consumer.consume(admin, cache)
        admin.commit()
    assert acked and store.get_epoch("MA") > ma_before and store.get_epoch("PV") == pv_before == 0
    with txn(db["users"]["app"], "MA") as conn:
        fresh, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
    assert hit is False and fresh.accepted_ids and set(fresh.accepted_ids) <= family["chunks"]["v2"]
    assert not set(fresh.accepted_ids) & family["chunks"]["v1"]
    assert all(e.historical is False for e in fresh.evidence)


def test_real_redis_publish_invalidation_refreshes_the_fact_plane(db, family, redis_url):
    import secrets

    import redis

    client = redis.Redis.from_url(redis_url, socket_connect_timeout=2, socket_timeout=2, decode_responses=True)
    namespace = f"medops-test:fact-plane:{secrets.token_hex(6)}:"
    store = RedisCandidateCacheStore(client, namespace=namespace)
    cache = CandidateCache(store, ttl_seconds=60, jitter=0)
    tag = family["tag"]
    try:
        with txn(db["users"]["app"], "MA") as conn:
            before, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
            assert hit is False and before.accepted_ids
            again, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
            assert hit is True and again.accepted_ids == before.accepted_ids
        with psycopg.connect(db["users"]["admin"]) as admin:
            publish_version(admin, family["k2"], AS_OF.replace(month=9, day=1), actor="reviewer-01", reason="v2")
            admin.commit()
        with txn(db["users"]["app"], "MA") as conn:
            stale, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
        assert hit is True and stale.evidence == ()
        epoch = store.get_epoch("MA")
        with psycopg.connect(db["users"]["admin"]) as admin:
            index_consumer.consume(admin, [index_consumer.tsvector_target(a.INDEX_TABLE, TOKENIZER)])
            acked = cache_consumer.consume(admin, cache)
            admin.commit()
        assert acked and store.get_epoch("MA") > epoch
        with txn(db["users"]["app"], "MA") as conn:
            fresh, hit = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
        assert hit is False and fresh.accepted_ids and set(fresh.accepted_ids) <= family["chunks"]["v2"]
    finally:
        keys = list(client.scan_iter(match=namespace + "*"))
        if keys:
            client.delete(*keys)
        client.close()


def test_version_or_date_changes_are_different_keys(db, family):
    cache = CandidateCache(InMemoryCandidateCacheStore())
    tag = family["tag"]
    with txn(db["users"]["app"], "MA") as conn:
        _, hit0 = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
        _, hit1 = fetch_evidence(conn, cache, _inputs(tag, retrieval_version=R2), _compute(conn, tag))
        _, hit2 = fetch_evidence(conn, cache, _inputs(tag, policy_version="policy-v2"), _compute(conn, tag))
        _, hit3 = fetch_evidence(conn, cache, _inputs(tag, as_of=AS_OF.replace(day=21)), _compute(conn, tag))
        _, hit4 = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
    assert (hit0, hit1, hit2, hit3, hit4) == (False, False, False, False, True)


def test_candidates_computed_under_one_identity_are_never_served_to_another(db, family):
    cache = CandidateCache(InMemoryCandidateCacheStore())
    tag = family["tag"]
    with txn(db["users"]["app"], "MA") as conn:
        ma, _ = fetch_evidence(conn, cache, _inputs(tag), _compute(conn, tag))
        assert ma.evidence
    co = UserContext(user_id="u-co", dept=Dept.CO, acl_scopes=frozenset({"CO:read"}))
    with txn(db["users"]["app"], "CO") as conn:
        result, hit = fetch_evidence(conn, cache, _inputs(tag, user=co), _compute(conn, tag))
    assert hit is False and result.evidence == () and result.rejected == ()  # CO's own retrieval found nothing
    assert cache.lookup(_inputs(tag, user=co)).candidates == ()
