"""ADR-0002 candidate A on the real schema with real LOGIN users: adapter contract (M1-03), zero
cross-department leakage including counts, zero silent shortfall, status/effective-time filtering inside
the query, version refusal, connection-pool identity reuse and execution-plan evidence (M1-04 for A).

Synthetic corpus only: no probe query is read or executed here. The module owns a separate database
because its seeds leave active documents behind (non-draft documents cannot be deleted), which would
break the exact-visibility assertions of test_rls in the shared session database."""

from __future__ import annotations

import json
import secrets
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, timedelta
from urllib.parse import urlsplit

import psycopg
import pytest
from psycopg import errors

from medops.core.errors import BusinessError, ErrorCode
from medops.infrastructure.db.login_users import GROUPS, drop_users, provision
from medops.retrieval.contracts import LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical import pg_simple_fts as a
from medops.retrieval.lexical.boundary import run_lexical_search
from tests.integration.conftest import _temporary_database, run_alembic, user_dsn
from tests.integration.test_migrations import document, job, source_object
from tests.unit.retrieval.lexical_contract import FIXTURE_TERMS, assert_lexical_adapter_contract, build_fixture_corpus

jieba = pytest.importorskip("jieba")
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1  # noqa: E402

DEPTS = ("MA", "PV", "CO")
AS_OF = date(2026, 6, 1)
TOKENIZER = JiebaTokenizerV1()
CONFIGURED = a.configured_versions(TOKENIZER)
FIXTURE_BASE = 0x0F000000_0000_4000_8000_000000000000  # deterministic, monotonic UUIDs for the contract corpus


def fixture_uuid(i: int) -> uuid.UUID:
    return uuid.UUID(int=FIXTURE_BASE + i)


# ------------------------------------------------------------------------------------ fixtures


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    gen = _temporary_database(admin_dsn)
    dsn = next(gen)
    run_alembic(dsn, "upgrade", "head")
    prefix = f"lx{secrets.token_hex(3)}"
    passwords = {kind: secrets.token_urlsafe(18) for kind in GROUPS}
    with psycopg.connect(admin_dsn) as conn:
        names = provision(conn, prefix=prefix, passwords=passwords)
        conn.commit()
    dbname = urlsplit(dsn).path.lstrip("/")
    users = {kind: user_dsn(admin_dsn, names[kind], passwords[kind], dbname) for kind in GROUPS}
    try:
        yield {"owner": dsn, "users": users}
    finally:
        with psycopg.connect(admin_dsn, autocommit=True) as conn:
            conn.execute(
                "select pg_terminate_backend(pid) from pg_stat_activity where usename = any(%s) and pid <> pg_backend_pid()",
                (list(names.values()),),
            )
            drop_users(conn, prefix=prefix)
        next(gen, None)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    """Per department: two active documents (3 chunks with 'sigma'), one archived, one draft, one not yet
    effective and one expired document (each with one 'sigma' chunk), plus one active document shared by MA
    and PV, plus the contract-harness corpus (25 chunks, deterministic UUIDs) owned by CO. Index installed
    by the owner and built through the admin LOGIN user (grants, not superuser powers)."""
    data: dict = {"eligible": {d: set() for d in DEPTS}, "excluded": {d: set() for d in DEPTS}, "fixture": {}}
    counter = 5000
    with psycopg.connect(db["owner"]) as conn:
        a.install(conn)

        def make(dept: str, status: str, acl: tuple[str, ...], texts: list[str], **when) -> list[uuid.UUID]:
            nonlocal counter
            counter += 1
            src = source_object(conn, counter)
            kwargs = {"family_id": uuid.uuid4(), "owner_dept": dept, "status": status, "version": f"v{counter}"}
            if status == "draft":
                doc = document(conn, src, None, **kwargs)
            else:
                doc = document(conn, src, job(conn, src), **{"effective_from": date(2026, 1, 1), **kwargs, **when})
            for d in acl:
                conn.execute(
                    "insert into document_acl (doc_id, dept, granted_by) values (%s, %s, 'admin-01')", (doc, d)
                )
            ids = []
            for seq, text in enumerate(texts):
                cid = conn.execute(
                    "insert into chunks (doc_id, seq, page, content, chunk_content_hash) values (%s, %s, 1, %s, null) returning chunk_id",
                    (doc, seq, text),
                ).fetchone()[0]
                ids.append(cid)
            return ids

        for dept in DEPTS:
            same = [f"sigma 研究 PROT-2024-017 30 mg {dept}", "sigma 随访 tau"]
            data["eligible"][dept] |= set(make(dept, "active", (dept,), same))
            data["eligible"][dept] |= set(make(dept, "active", (dept,), ["sigma 研究"]))
            data["excluded"][dept] |= set(make(dept, "archived", (dept,), ["sigma archived"]))
            data["excluded"][dept] |= set(make(dept, "draft", (dept,), ["sigma draft"]))
            data["future"] = make(dept, "active", (dept,), ["sigma future"], effective_from=AS_OF + timedelta(days=1))
            data["excluded"][dept] |= set(data["future"])
            data["expired"] = make(dept, "active", (dept,), ["sigma expired"], effective_to=AS_OF)
            data["excluded"][dept] |= set(data["expired"])
        shared = make("MA", "active", ("MA", "PV"), ["sigma shared"])
        data["eligible"]["MA"] |= set(shared)
        data["eligible"]["PV"] |= set(shared)
        # contract corpus in CO with deterministic UUIDs (fixture order == UUID order == chunk_id order)
        counter += 1
        src = source_object(conn, counter)
        doc = document(
            conn,
            src,
            job(conn, src),
            family_id=uuid.uuid4(),
            owner_dept="CO",
            status="active",
            version="fixture",
            effective_from=date(2026, 1, 1),
        )
        conn.execute("insert into document_acl (doc_id, dept, granted_by) values (%s, 'CO', 'admin-01')", (doc,))
        for i, chunk in enumerate(build_fixture_corpus()):
            cid = fixture_uuid(i)
            conn.execute(
                "insert into chunks (chunk_id, doc_id, seq, page, content, chunk_content_hash) values (%s, %s, %s, 1, %s, null)",
                (cid, doc, i, chunk.text),
            )
            data["fixture"][str(cid)] = chunk.chunk_id
        data["total_chunks"] = conn.execute("select count(*) from chunks").fetchone()[0]
        conn.commit()
    with psycopg.connect(db["users"]["admin"]) as conn:
        data["report"] = a.build_index(conn, TOKENIZER, built_by="test-admin-01")
        conn.commit()
    return data


@contextmanager
def txn(dsn: str, dept: str | None) -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            if dept is not None:
                conn.execute("select set_config('medops.dept', %s, true)", (dept,))
            yield conn


def search(dsn: str, dept: str | None, query: str, k: int, *, as_of: date | None = AS_OF) -> LexicalSearchResult:
    with txn(dsn, dept) as conn:
        return run_lexical_search(a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=as_of), query, k, expected=CONFIGURED)


def ids(result: LexicalSearchResult) -> set[uuid.UUID]:
    return {uuid.UUID(c.chunk_id) for c in result.candidates}


# --------------------------------------------------------------------------------------- tests


def test_install_is_idempotent_and_tables_are_force_rls_with_least_grants(db, seed):
    with psycopg.connect(db["owner"]) as conn:
        a.install(conn)  # second run: no error, nothing lost
        conn.commit()
        for table in (a.META_TABLE, a.INDEX_TABLE):
            rls = conn.execute(
                "select relrowsecurity, relforcerowsecurity from pg_class where relname = %s", (table,)
            ).fetchone()
            assert rls == (True, True), table
            grants = {
                (r[0], r[1])
                for r in conn.execute(
                    "select grantee, privilege_type from information_schema.role_table_grants where table_name = %s",
                    (table,),
                )
            }
            for role in ("medops_app", "medops_readonly"):
                assert {p for g, p in grants if g == role} == {"SELECT"}, (table, role)
            assert {p for g, p in grants if g == "medops_admin_role"} == {"SELECT", "INSERT", "UPDATE", "DELETE"}
        assert conn.execute(f"select count(*) from {a.INDEX_TABLE}").fetchone()[0] == seed["report"].chunk_count


def test_build_indexes_every_chunk_and_records_the_versions(db, seed):
    report = seed["report"]
    assert report.chunk_count == seed["total_chunks"] and report.skipped_empty == 0
    assert report.versions == CONFIGURED
    with txn(db["users"]["app"], "MA") as conn:
        assert a.PgSimpleFtsRetriever(conn, TOKENIZER).versions == CONFIGURED


def test_adapter_contract_on_postgres_under_the_app_role(db, seed):
    to_fixture = seed["fixture"]

    class Mapped:
        """The harness speaks fixture ids (c000..); UUIDs were chosen so their order matches."""

        def __init__(self, inner: a.PgSimpleFtsRetriever) -> None:
            self.inner = inner

        @property
        def versions(self) -> LexicalVersions:
            return self.inner.versions

        def search(self, query: str, k: int) -> LexicalSearchResult:
            r = self.inner.search(query, k)
            mapped = tuple(c.model_copy(update={"chunk_id": to_fixture[c.chunk_id]}) for c in r.candidates)
            return r.model_copy(update={"candidates": mapped})

    with txn(db["users"]["app"], "CO") as conn:
        assert_lexical_adapter_contract(lambda corpus: Mapped(a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=AS_OF)))


@pytest.mark.parametrize("kind", ["app", "readonly"])
@pytest.mark.parametrize("dept", DEPTS)
def test_zero_cross_department_leakage_including_counts(db, seed, kind, dept):
    dsn = db["users"][kind]
    expected = seed["eligible"][dept]
    result = search(dsn, dept, "sigma", 20)
    n = len(expected)  # MA and PV: 3 own + 1 shared; CO: 3 own
    assert n == (4 if dept in ("MA", "PV") else 3)
    assert ids(result) == expected
    assert result.returned_count == n and result.candidate_exhausted is True
    others = set().union(*(seed["eligible"][d] | seed["excluded"][d] for d in DEPTS if d != dept)) - expected
    assert not ids(result) & others
    # the count never reveals other departments' rows: k == own count is "not exhausted", k + 1 is
    assert search(dsn, dept, "sigma", n).candidate_exhausted is False
    assert search(dsn, dept, "sigma", n - 1).candidate_exhausted is False
    assert search(dsn, dept, "sigma", n + 1).candidate_exhausted is True


def test_status_and_effective_window_are_filtered_inside_the_query(db, seed):
    dsn = db["users"]["app"]
    for dept in DEPTS:
        assert not ids(search(dsn, dept, "sigma", 20)) & seed["excluded"][dept]
    # as_of moves the window: the day before, the expired document is still effective; the day after,
    # the future one becomes effective (the last department seeded is CO)
    before = search(dsn, "CO", "sigma", 20, as_of=AS_OF - timedelta(days=1))
    after = search(dsn, "CO", "sigma", 20, as_of=AS_OF + timedelta(days=1))
    assert ids(before) == seed["eligible"]["CO"] | set(seed["expired"])
    assert ids(after) == seed["eligible"]["CO"] | set(seed["future"])


def test_missing_identity_or_transaction_is_refused_not_empty(db, seed):
    dsn = db["users"]["app"]
    with pytest.raises(BusinessError) as exc:
        search(dsn, None, "sigma", 20)
    assert exc.value.code is ErrorCode.unauthenticated
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("select set_config('medops.dept', 'MA', false)")  # session-level, but no transaction
        with pytest.raises(BusinessError) as exc2:
            a.PgSimpleFtsRetriever(conn, TOKENIZER).search("sigma", 20)
        assert exc2.value.code is ErrorCode.unauthenticated


def test_connection_reuse_does_not_carry_identity_over(db, seed):
    dsn = db["users"]["app"]
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            conn.execute("select set_config('medops.dept', 'MA', true)")
            assert a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=AS_OF).search("sigma", 20).returned_count == 4
        with conn.transaction():  # next request on the same pooled connection, no identity injected
            with pytest.raises(BusinessError) as exc:
                a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=AS_OF).search("sigma", 20)
            assert exc.value.code is ErrorCode.unauthenticated
        conn.execute("select set_config('medops.dept', 'PV', false)")
        conn.commit()
        conn.execute("reset all")
        conn.commit()
        with conn.transaction():
            with pytest.raises(BusinessError):
                a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=AS_OF).search("sigma", 20)


def test_k_boundaries_never_shortfall_silently_under_either_plan(db, seed):
    dsn = db["users"]["app"]
    cases = {("gamma", 6): (6, False), ("gamma", 7): (7, False), ("gamma", 8): (7, True), ("delta", 20): (20, False)}
    for seqscan in ("off", "on"):
        with txn(dsn, "CO") as conn:
            conn.execute(f"set local enable_seqscan = {seqscan}")
            retriever = a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=AS_OF)
            for (term, k), (count, exhausted) in cases.items():
                r = run_lexical_search(retriever, term, k, expected=CONFIGURED)
                assert (r.returned_count, r.candidate_exhausted) == (count, exhausted), (term, k, seqscan)
                assert {seed["fixture"][c.chunk_id] for c in r.candidates} <= {
                    f"c{i:03d}" for i in range(FIXTURE_TERMS[term])
                }


def test_ties_break_by_chunk_id_and_repeated_runs_are_identical(db, seed):
    dsn = db["users"]["app"]
    first = search(dsn, "CO", "beta", 20)
    assert first.returned_count == 3 and len({c.raw_score for c in first.candidates}) == 1
    assert [c.chunk_id for c in first.candidates] == sorted(c.chunk_id for c in first.candidates)
    for _ in range(3):
        assert search(dsn, "CO", "beta", 20) == first


def test_query_without_tokens_yields_zero_eligible_candidates(db, seed):
    r = search(db["users"]["app"], "MA", "!!!", 20)
    assert r.returned_count == 0 and r.candidate_exhausted is True


def test_version_mismatch_is_refused_by_adapter_and_boundary(db, seed, tmp_path):
    user_dict = tmp_path / "med.dict"
    user_dict.write_text("美洛醣 10 n\n", encoding="utf-8")
    drifted = JiebaTokenizerV1(user_dictionary=user_dict)
    assert drifted.dictionary_version != TOKENIZER.dictionary_version
    with txn(db["users"]["app"], "MA") as conn:
        retriever = a.PgSimpleFtsRetriever(conn, drifted, as_of=AS_OF)
        assert retriever.versions == CONFIGURED  # what the index was built with, not the drifted query config
        with pytest.raises(BusinessError) as exc:
            retriever.search("sigma", 20)
        assert exc.value.code is ErrorCode.version_conflict
        with pytest.raises(BusinessError) as exc2:
            run_lexical_search(retriever, "sigma", 20, expected=a.configured_versions(drifted))
        assert exc2.value.code is ErrorCode.version_conflict


def test_explain_under_the_app_role_uses_the_gin_index_and_policy_filters(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        conn.execute("set local enable_seqscan = off")
        plan = a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=AS_OF).explain("sigma 研究", 20)
    tree = json.loads(plan)
    assert tree and tree[0]["Plan"]["Node Type"] == "Limit"
    # the statement is planned over the index table with the RLS policy chain (chunks -> documents ->
    # document_acl with the transaction's department) inside the plan, not applied afterwards
    assert a.INDEX_TABLE in plan and "document_acl" in plan
    assert "medops_current_dept" in plan or "current_setting('medops.dept'" in plan  # the SQL function is inlined
    assert "@@" in plan and "effective_from" in plan
    # status = 'active' is either a visible filter or satisfied through the partial unique index on active rows
    assert "'active'" in plan or "documents_one_active_per_family" in plan
    # on a table this small the planner may drive from the RLS side; a bitmap scan on the GIN index must
    # at least be planned when the table is the only reasonable access path
    with txn(db["users"]["app"], "MA") as conn:
        conn.execute("set local enable_seqscan = off")
        conn.execute("set local enable_indexscan = off")
        gin_plan = a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=AS_OF).explain("sigma 研究", 20)
    assert f"{a.INDEX_TABLE}_tsv_gin" in gin_plan or "Bitmap" in gin_plan


def test_app_and_readonly_roles_cannot_write_the_index(db, seed):
    some = next(iter(seed["eligible"]["MA"]))
    for kind in ("app", "readonly"):
        with psycopg.connect(db["users"][kind]) as conn:
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(f"delete from {a.INDEX_TABLE} where chunk_id = %s", (some,))
            conn.rollback()
            with pytest.raises(errors.InsufficientPrivilege):
                conn.execute(f"update {a.META_TABLE} set chunk_count = 0")
            conn.rollback()


def test_literals_round_trip_through_postgres(db, seed):
    tokens = ["it's", "a\\b", "美洛醣", "prot-2024-017", "30", "it's"]
    with psycopg.connect(db["owner"]) as conn:
        stored = conn.execute("select tsvector_to_array(%s::tsvector)", (a.tsvector_literal(tokens),)).fetchone()[0]
        assert set(stored) == set(tokens)
        positions = conn.execute("select %s::tsvector::text", (a.tsvector_literal(tokens),)).fetchone()[0]
        assert "'it''s':1,6" in positions
        for token in set(tokens):
            hit = conn.execute(
                "select %s::tsvector @@ %s::tsquery", (a.tsvector_literal(tokens), a.tsquery_literal([token]))
            ).fetchone()[0]
            assert hit is True, token
        assert (
            conn.execute(
                "select %s::tsvector @@ %s::tsquery", (a.tsvector_literal(tokens), a.tsquery_literal(["zzz"]))
            ).fetchone()[0]
            is False
        )


def test_rebuild_through_the_admin_login_user_replaces_the_index(db, seed):
    with psycopg.connect(db["users"]["admin"]) as conn:
        report = a.build_index(conn, TOKENIZER, built_by="test-admin-02")
        conn.commit()
        assert report.chunk_count == seed["report"].chunk_count
        assert conn.execute(f"select built_by, chunk_count from {a.META_TABLE}").fetchone() == (
            "test-admin-02",
            report.chunk_count,
        )
