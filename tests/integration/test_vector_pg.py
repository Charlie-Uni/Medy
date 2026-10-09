"""M1-16 pgvector adapter on the real schema (migration 0006), real LOGIN users and FORCE RLS: zero
cross-department leakage including counts, status/window filtering inside the query, exact `min(k, eligible)`
pages under the HNSW index, identity and version refusals, plan evidence and write protection. The hashing
test provider stands in for bge-m3 so the database side is tested without PyTorch."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import date

import psycopg
import pytest
from psycopg import errors

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.vector import pg_vector
from medops.retrieval.vector.boundary import run_vector_search
from medops.retrieval.vector.contracts import VectorVersions
from medops.retrieval.vector.embedding import HashingEmbeddingProvider
from tests.integration.lexical_adapter_suite import AS_OF, DEPTS, CandidateUnderTest, make_database, seed_candidate, txn

PROVIDER = HashingEmbeddingProvider()

CUT = CandidateUnderTest(
    name="V",
    index_table=pg_vector.TABLE,
    install=lambda conn: None,  # migration 0006 creates the tables
    build=lambda conn, built_by: pg_vector.build_index(conn, PROVIDER, built_by=built_by),  # type: ignore[arg-type,return-value]
    make_retriever=lambda conn, as_of: pg_vector.PgVectorRetriever(conn, PROVIDER, as_of=as_of),
    expected_versions=lambda conn: pg_vector.PgVectorRetriever(conn, PROVIDER).configured,  # type: ignore[arg-type,return-value]
    make_drifted_retriever=lambda conn, as_of, tmp: None,
    drifted_versions=lambda conn, tmp: None,  # type: ignore[arg-type,return-value]
    index_plan_markers=(pg_vector.INDEX_NAME,),
)


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    data = seed_candidate(db, CUT)
    with psycopg.connect(db["owner"]) as conn:
        data["visible"] = {
            dept: {
                r[0]
                for r in conn.execute(
                    """select e.chunk_id from chunk_embeddings e
                       join chunks c on c.chunk_id = e.chunk_id
                       join documents d on d.doc_id = c.doc_id
                       join document_acl a on a.doc_id = d.doc_id and a.permission = 'read'
                       where a.dept = %s and e.embedding_version = %s and d.status = 'active'
                         and d.effective_from <= %s and (d.effective_to is null or d.effective_to > %s)""",
                    (dept, PROVIDER.spec.embedding_version, AS_OF, AS_OF),
                )
            }
            for dept in DEPTS
        }
        data["all_chunks"] = {r[0] for r in conn.execute("select chunk_id from chunks")}
    return data


def retriever(conn, as_of=AS_OF):
    return pg_vector.PgVectorRetriever(conn, PROVIDER, as_of=as_of)


def test_build_embeds_every_chunk_records_the_spec_and_is_idempotent(db, seed):
    report = seed["report"]
    assert report.chunk_count == seed["total_chunks"] == report.embedded_now
    with psycopg.connect(db["users"]["admin"]) as admin:
        again = pg_vector.build_index(admin, PROVIDER, built_by="test-admin-01")
        assert again.embedded_now == 0 and again.chunk_count == seed["total_chunks"]
        meta = pg_vector.read_meta(admin, PROVIDER.spec.embedding_version)
        assert meta == PROVIDER.spec
        admin.rollback()


@pytest.mark.parametrize("kind", ["app", "readonly"])
@pytest.mark.parametrize("dept", DEPTS)
def test_zero_cross_department_leakage_including_counts(db, seed, kind, dept):
    with txn(db["users"][kind], dept) as conn:
        r = retriever(conn)
        assert r.eligible_count() == len(seed["visible"][dept])
        result = r.search("sigma", 100)
    ids = {uuid.UUID(c.chunk_id) for c in result.candidates}
    assert ids == seed["visible"][dept]
    assert result.returned_count == len(ids) and result.candidate_exhausted is True
    for other in DEPTS:
        if other != dept:
            assert not ids & (seed["visible"][other] - seed["visible"][dept])


def test_status_and_effective_window_are_filtered_inside_the_query(db, seed):
    excluded = set().union(*seed["excluded"].values())
    for dept in DEPTS:
        with txn(db["users"]["app"], dept) as conn:
            result = retriever(conn).search("sigma", 100)
        assert not {uuid.UUID(c.chunk_id) for c in result.candidates} & excluded
    with txn(db["users"]["app"], "MA") as conn:
        past = retriever(conn, as_of=date(2020, 1, 1)).search("sigma", 5)
    assert past.candidates == () and past.candidate_exhausted is True


def test_archived_versions_are_returned_only_on_explicit_historical_requests(db, seed):
    """Record 71: the vector channel admits archived versions only when the caller asked for historical evidence."""
    for dept in DEPTS:
        with txn(db["users"]["app"], dept) as conn:
            plain = {uuid.UUID(c.chunk_id) for c in retriever(conn).search("sigma", 100).candidates}
            historical = {
                uuid.UUID(c.chunk_id) for c in retriever(conn).search("sigma", 100, allow_historical=True).candidates
            }
        assert not plain & seed["archived"][dept]
        assert seed["archived"][dept] <= historical
        assert not historical & (seed["excluded"][dept] - seed["archived"][dept])


def test_pages_are_exactly_min_k_eligible_under_the_hnsw_index(db, seed):
    n = len(seed["visible"]["MA"])
    assert n >= 3
    with txn(db["users"]["app"], "MA") as conn:
        for k in (1, n - 1, n, n + 1, 50):
            result = retriever(conn).search("sigma 研究", k)
            assert result.returned_count == min(k, n) and result.candidate_exhausted is (n < k), k
            scores = [c.raw_score for c in result.candidates]
            assert scores == sorted(scores, reverse=True)


def test_semantics_ranking_ties_and_reproducibility(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        r = retriever(conn)
        runs = [r.search("sigma 随访 tau", 4) for _ in range(3)]
        top = conn.execute(
            "select content from chunks where chunk_id = %s", (runs[0].candidates[0].chunk_id,)
        ).fetchone()[0]
    assert top == "sigma 随访 tau"
    assert [[c.chunk_id for c in run.candidates] for run in runs] == [[c.chunk_id for c in runs[0].candidates]] * 3
    for a, b in zip(runs[0].candidates, runs[0].candidates[1:], strict=False):
        assert (
            (a.raw_score, a.chunk_id) >= (b.raw_score, b.chunk_id)
            if a.raw_score == b.raw_score
            else a.raw_score > b.raw_score
        )


@pytest.mark.parametrize(
    ("mode", "version", "generic_count", "custom_count"),
    [
        ("force_generic_plan", pg_vector.GENERIC_PLAN_RETRIEVER_VERSION, 3, 0),
        ("force_custom_plan", pg_vector.CUSTOM_PLAN_RETRIEVER_VERSION, 0, 3),
    ],
)
def test_plan_policy_is_versioned_used_and_restores_transaction_setting(
    db, seed, mode, version, generic_count, custom_count
):
    with txn(db["users"]["app"], "MA") as conn:
        conn.execute("set local plan_cache_mode = force_custom_plan")
        before = conn.execute("show plan_cache_mode").fetchone()[0]
        candidate = pg_vector.PgVectorRetriever(
            conn,
            PROVIDER,
            as_of=AS_OF,
            plan_cache_mode=mode,
        )
        runs = [candidate.search("sigma 随访 tau", 4) for _ in range(3)]
        after = conn.execute("show plan_cache_mode").fetchone()[0]
        counts = conn.execute(
            "select generic_plans, custom_plans from pg_prepared_statements "
            "where statement like '%%select e.chunk_id, e.embedding <=>%%'"
        ).fetchone()
    assert candidate.configured.retriever_version == version
    assert [run.retriever_version for run in runs] == [version] * 3
    assert [[c.chunk_id for c in run.candidates] for run in runs] == [[c.chunk_id for c in runs[0].candidates]] * 3
    assert after == before
    assert counts == (generic_count, custom_count)


@pytest.mark.parametrize("mode", ["force_generic_plan", "force_custom_plan"])
def test_forced_plan_reuse_preserves_department_history_and_document_filters(db, seed, mode):
    with psycopg.connect(db["owner"]) as admin:
        doc_by_chunk = dict(admin.execute("select chunk_id, doc_id from chunks"))
    # The same prepared search is reused across departments, history flags and document restrictions.
    with psycopg.connect(db["users"]["app"]) as conn:
        for dept in DEPTS:
            for historical in (False, True):
                visible = seed["visible"][dept] | (seed["archived"][dept] if historical else set())
                one_doc = doc_by_chunk[min(visible)]
                for doc_ids in (None, [str(one_doc)]):
                    expected = visible if doc_ids is None else {c for c in visible if doc_by_chunk[c] == one_doc}
                    with conn.transaction():
                        conn.execute("select set_config('medops.dept', %s, true)", (dept,))
                        result = pg_vector.PgVectorRetriever(conn, PROVIDER, as_of=AS_OF, plan_cache_mode=mode).search(
                            "sigma", 100, allow_historical=historical, doc_ids=doc_ids
                        )
                    assert {uuid.UUID(c.chunk_id) for c in result.candidates} == expected
                    assert result.returned_count == len(expected)


def test_missing_identity_or_transaction_is_refused_not_empty(db, seed):
    with txn(db["users"]["app"], None) as conn:
        with pytest.raises(BusinessError) as exc:
            retriever(conn).search("sigma", 5)
        assert exc.value.code is ErrorCode.unauthenticated
    with psycopg.connect(db["users"]["app"], autocommit=True) as conn:
        with pytest.raises(BusinessError) as exc:
            retriever(conn).search("sigma", 5)
        assert exc.value.code is ErrorCode.unauthenticated


def test_version_and_spec_mismatches_are_refused_by_adapter_boundary_and_builder(db, seed):
    other_version = HashingEmbeddingProvider(embedding_version="emb-hash-test-v2")
    with txn(db["users"]["app"], "MA") as conn:
        with pytest.raises(InfrastructureError) as exc:
            _ = pg_vector.PgVectorRetriever(conn, other_version, as_of=AS_OF).versions
        assert exc.value.code is ErrorCode.dependency_unavailable
        r = retriever(conn)
        with pytest.raises(BusinessError) as exc2:
            run_vector_search(
                r, "sigma", 5, expected=r.configured.model_copy(update={"embedding_version": "emb-hash-test-v2"})
            )
        assert exc2.value.code is ErrorCode.version_conflict
        assert run_vector_search(r, "sigma", 5, expected=r.configured).returned_count == 4
    drifted = HashingEmbeddingProvider()
    drifted._spec = drifted.spec.model_copy(update={"max_seq_length": 512})  # same version, other truncation
    with psycopg.connect(db["users"]["admin"]) as admin:
        with pytest.raises(BusinessError) as exc3:
            pg_vector.build_index(admin, drifted, built_by="test-admin-01")
        assert exc3.value.code is ErrorCode.version_conflict
        admin.rollback()
    with txn(db["users"]["app"], "MA") as conn:
        with pytest.raises(BusinessError) as exc4:
            pg_vector.PgVectorRetriever(conn, drifted, as_of=AS_OF).search("sigma", 5)
        assert exc4.value.code is ErrorCode.version_conflict


def test_explain_under_the_app_role_shows_the_policy_chain_and_the_hnsw_index(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        default_plan = retriever(conn).explain("sigma", 5)
        # on a table this small the planner prefers an exact pkey scan + sort; forcing it off proves the
        # ordered HNSW path exists behind the same RLS chain (the exact-count guard covers either plan)
        conn.execute("set local enable_seqscan = off")
        conn.execute("set local enable_sort = off")
        forced_plan = retriever(conn).explain("sigma", 5)
    for plan in (default_plan, forced_plan):
        assert '"documents"' in plan and '"chunks"' in plan and "document_acl" in plan and "medops.dept" in plan
        json.loads(plan)
    assert pg_vector.INDEX_NAME in forced_plan


def test_ordinary_roles_cannot_write_embeddings_or_metadata(db, seed):
    some = next(iter(seed["all_chunks"]))
    for kind in ("app", "readonly"):
        with psycopg.connect(db["users"][kind]) as conn:
            for sql, params in (
                ("delete from chunk_embeddings where chunk_id = %s", (some,)),
                ("update embedding_index_meta set chunk_count = 0", ()),
                (
                    "insert into embedding_index_meta (embedding_version, model_id, model_revision, dimension, normalization, max_seq_length, framework, chunk_count, built_by) values ('x','m','r',1024,'l2',1,'f',0,'b')",
                    (),
                ),
            ):
                with pytest.raises(errors.InsufficientPrivilege):
                    conn.execute(sql, params)
                conn.rollback()


def test_vector_tables_are_force_rls_with_least_grants(db, seed):
    with psycopg.connect(db["owner"]) as conn:
        forced = {
            r[0]
            for r in conn.execute(
                "select relname from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname='public' and relkind='r' and relforcerowsecurity"
            )
        }
        assert {"chunk_embeddings", "embedding_index_meta"} <= forced
        grants = conn.execute(
            "select grantee, table_name, privilege_type from information_schema.role_table_grants where table_name in ('chunk_embeddings','embedding_index_meta') and grantee in ('medops_app','medops_readonly') order by 1,2,3"
        ).fetchall()
        assert {g[2] for g in grants} == {"SELECT"}
        expected = VectorVersions(
            retriever_version=pg_vector.RETRIEVER_VERSION,
            embedding_version=PROVIDER.spec.embedding_version,
            normalization_version="norm-v1",
        )
    with txn(db["users"]["app"], "MA") as conn:
        assert retriever(conn).versions == expected
