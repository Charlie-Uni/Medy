"""Shared integration suite for the PostgreSQL lexical candidates of ADR-0002 (M1-03 adapter contract,
M1-04 gates): zero cross-department leakage including counts, zero silent shortfall, status and
effective-time filtering inside the query, identity and version refusal, connection-pool identity reuse
and execution-plan evidence. Synthetic corpus only: no probe query is read or executed.

A candidate module plugs in through `CandidateUnderTest`; the concrete test module supplies the `db`
(server + temporary database + LOGIN users) and `seed` fixtures and subclasses `LexicalAdapterSuite`.
Every candidate runs in its own temporary database because the seeds leave active documents behind
(non-draft documents cannot be deleted), which would break test_rls' exact-visibility assertions."""

from __future__ import annotations

import json
import os
import secrets
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import psycopg
import pytest
from psycopg import errors

from medops.core.errors import BusinessError, ErrorCode
from medops.infrastructure.db.login_users import GROUPS, drop_users, provision
from medops.retrieval.contracts import LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical.boundary import run_lexical_search
from medops.retrieval.lexical.pg_lexical_common import META_TABLE, IndexBuildReport
from tests.integration.conftest import _temporary_database, run_alembic, user_dsn
from tests.integration.test_migrations import document, job, source_object
from tests.unit.retrieval.lexical_contract import FIXTURE_TERMS, assert_lexical_adapter_contract, build_fixture_corpus

REPO = Path(__file__).resolve().parents[2]
DEPTS = ("MA", "PV", "CO")
AS_OF = date(2026, 6, 1)
FIXTURE_BASE = 0x0F000000_0000_4000_8000_000000000000  # deterministic, monotonic UUIDs for the contract corpus


@dataclass(frozen=True)
class CandidateUnderTest:
    name: str
    index_table: str
    install: Callable[[psycopg.Connection[Any]], None]
    build: Callable[[psycopg.Connection[Any], str], IndexBuildReport]  # (conn, built_by)
    make_retriever: Callable[[psycopg.Connection[Any], date | None], Any]
    expected_versions: Callable[[psycopg.Connection[Any]], LexicalVersions]
    make_drifted_retriever: Callable[[psycopg.Connection[Any], date | None, Path], Any]
    drifted_versions: Callable[[psycopg.Connection[Any], Path], LexicalVersions]
    index_plan_markers: tuple[str, ...]  # any of these must appear when the planner is pushed onto the index


def fixture_uuid(i: int) -> uuid.UUID:
    return uuid.UUID(int=FIXTURE_BASE + i)


# ------------------------------------------------------------------------------------ servers


def experiment_admin_dsn(candidate: str) -> str | None:
    """Superuser DSN of a candidate's own server: MEDOPS_TEST_<X>_ADMIN_URL, else DEC001_<X>_ADMIN_URL from
    the process environment or the local, gitignored `.env.dec001`. None when not configured."""
    key = f"DEC001_{candidate}_ADMIN_URL"
    explicit = os.environ.get(f"MEDOPS_TEST_{candidate}_ADMIN_URL") or os.environ.get(key)
    if explicit:
        return explicit
    env_file = REPO / ".env.dec001"
    if not env_file.is_file():
        return None
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.startswith(key + "="):
            return line.split("=", 1)[1].strip() or None
    return None


def require_server(candidate: str) -> str:
    dsn = experiment_admin_dsn(candidate)
    if not dsn:
        pytest.skip(
            f"candidate {candidate}: no DEC001_{candidate}_ADMIN_URL (.env.dec001) and no MEDOPS_TEST_{candidate}_ADMIN_URL"
        )
    try:
        psycopg.connect(dsn, connect_timeout=3).close()
    except psycopg.Error as exc:
        pytest.skip(f"candidate {candidate}: server unreachable ({type(exc).__name__})")
    return dsn


def make_database(admin_dsn: str) -> Iterator[dict]:
    """Temporary database migrated to head with three LOGIN users; dropped afterwards."""
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


# ------------------------------------------------------------------------------------ seed


def seed_candidate(db: dict, cut: CandidateUnderTest) -> dict:
    """Per department: two active documents (3 chunks with 'sigma'), one archived, one draft, one not yet
    effective and one expired document (each with one 'sigma' chunk), plus one active document shared by MA
    and PV, plus the contract-harness corpus (25 chunks, deterministic UUIDs) owned by CO. Index installed
    by the owner and built through the admin LOGIN user (grants, not superuser powers)."""
    data: dict = {"eligible": {d: set() for d in DEPTS}, "excluded": {d: set() for d in DEPTS}, "fixture": {}}
    counter = 5000
    with psycopg.connect(db["owner"]) as conn:
        cut.install(conn)

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
        data["report"] = cut.build(conn, "test-admin-01")
        conn.commit()
    return data


@contextmanager
def txn(dsn: str, dept: str | None) -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn) as conn:
        with conn.transaction():
            if dept is not None:
                conn.execute("select set_config('medops.dept', %s, true)", (dept,))
            yield conn


def ids(result: LexicalSearchResult) -> set[uuid.UUID]:
    return {uuid.UUID(c.chunk_id) for c in result.candidates}


# ------------------------------------------------------------------------------------ suite


class LexicalAdapterSuite:
    cut: CandidateUnderTest

    def search(
        self, dsn: str, dept: str | None, query: str, k: int, *, as_of: date | None = AS_OF
    ) -> LexicalSearchResult:
        with txn(dsn, dept) as conn:
            retriever = self.cut.make_retriever(conn, as_of)
            return run_lexical_search(retriever, query, k, expected=self.cut.expected_versions(conn))

    def test_install_is_idempotent_and_tables_are_force_rls_with_least_grants(self, db, seed):
        with psycopg.connect(db["owner"]) as conn:
            self.cut.install(conn)  # second run: no error, nothing lost
            conn.commit()
            for table in (META_TABLE, self.cut.index_table):
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
            assert (
                conn.execute(f"select count(*) from {self.cut.index_table}").fetchone()[0] == seed["report"].chunk_count
            )

    def test_build_indexes_every_chunk_and_records_the_versions(self, db, seed):
        report = seed["report"]
        assert report.chunk_count == seed["total_chunks"] and report.skipped_empty == 0
        with txn(db["users"]["app"], "MA") as conn:
            expected = self.cut.expected_versions(conn)
            assert report.versions == expected
            assert self.cut.make_retriever(conn, AS_OF).versions == expected

    def test_adapter_contract_on_postgres_under_the_app_role(self, db, seed):
        to_fixture = seed["fixture"]

        class Mapped:
            """The harness speaks fixture ids (c000..); UUIDs were chosen so their order matches."""

            def __init__(self, inner) -> None:
                self.inner = inner

            @property
            def versions(self) -> LexicalVersions:
                return self.inner.versions

            def search(self, query: str, k: int) -> LexicalSearchResult:
                r = self.inner.search(query, k)
                mapped = tuple(c.model_copy(update={"chunk_id": to_fixture[c.chunk_id]}) for c in r.candidates)
                return r.model_copy(update={"candidates": mapped})

        with txn(db["users"]["app"], "CO") as conn:
            assert_lexical_adapter_contract(lambda corpus: Mapped(self.cut.make_retriever(conn, AS_OF)))

    @pytest.mark.parametrize("kind", ["app", "readonly"])
    @pytest.mark.parametrize("dept", DEPTS)
    def test_zero_cross_department_leakage_including_counts(self, db, seed, kind, dept):
        dsn = db["users"][kind]
        expected = seed["eligible"][dept]
        n = len(expected)  # MA and PV: 3 own + 1 shared; CO: 3 own
        assert n == (4 if dept in ("MA", "PV") else 3)
        result = self.search(dsn, dept, "sigma", 20)
        assert ids(result) == expected
        assert result.returned_count == n and result.candidate_exhausted is True
        others = set().union(*(seed["eligible"][d] | seed["excluded"][d] for d in DEPTS if d != dept)) - expected
        assert not ids(result) & others
        assert self.search(dsn, dept, "sigma", n).candidate_exhausted is False
        assert self.search(dsn, dept, "sigma", n - 1).candidate_exhausted is False
        assert self.search(dsn, dept, "sigma", n + 1).candidate_exhausted is True

    def test_status_and_effective_window_are_filtered_inside_the_query(self, db, seed):
        dsn = db["users"]["app"]
        for dept in DEPTS:
            assert not ids(self.search(dsn, dept, "sigma", 20)) & seed["excluded"][dept]
        before = self.search(dsn, "CO", "sigma", 20, as_of=AS_OF - timedelta(days=1))
        after = self.search(dsn, "CO", "sigma", 20, as_of=AS_OF + timedelta(days=1))
        assert ids(before) == seed["eligible"]["CO"] | set(seed["expired"])
        assert ids(after) == seed["eligible"]["CO"] | set(seed["future"])

    def test_missing_identity_or_transaction_is_refused_not_empty(self, db, seed):
        dsn = db["users"]["app"]
        with pytest.raises(BusinessError) as exc:
            self.search(dsn, None, "sigma", 20)
        assert exc.value.code is ErrorCode.unauthenticated
        with psycopg.connect(dsn, autocommit=True) as conn:
            conn.execute("select set_config('medops.dept', 'MA', false)")  # session-level, but no transaction
            with pytest.raises(BusinessError) as exc2:
                self.cut.make_retriever(conn, AS_OF).search("sigma", 20)
            assert exc2.value.code is ErrorCode.unauthenticated

    def test_connection_reuse_does_not_carry_identity_over(self, db, seed):
        dsn = db["users"]["app"]
        with psycopg.connect(dsn) as conn:
            with conn.transaction():
                conn.execute("select set_config('medops.dept', 'MA', true)")
                assert self.cut.make_retriever(conn, AS_OF).search("sigma", 20).returned_count == 4
            with conn.transaction():  # next request on the same pooled connection, no identity injected
                with pytest.raises(BusinessError) as exc:
                    self.cut.make_retriever(conn, AS_OF).search("sigma", 20)
                assert exc.value.code is ErrorCode.unauthenticated
            conn.execute("select set_config('medops.dept', 'PV', false)")
            conn.commit()
            conn.execute("reset all")
            conn.commit()
            with conn.transaction():
                with pytest.raises(BusinessError):
                    self.cut.make_retriever(conn, AS_OF).search("sigma", 20)

    def test_k_boundaries_never_shortfall_silently_under_either_plan(self, db, seed):
        dsn = db["users"]["app"]
        cases = {
            ("gamma", 6): (6, False),
            ("gamma", 7): (7, False),
            ("gamma", 8): (7, True),
            ("delta", 20): (20, False),
        }
        for seqscan in ("off", "on"):
            with txn(dsn, "CO") as conn:
                conn.execute(f"set local enable_seqscan = {seqscan}")
                retriever = self.cut.make_retriever(conn, AS_OF)
                expected = self.cut.expected_versions(conn)
                for (term, k), (count, exhausted) in cases.items():
                    r = run_lexical_search(retriever, term, k, expected=expected)
                    assert (r.returned_count, r.candidate_exhausted) == (count, exhausted), (term, k, seqscan)
                    assert {seed["fixture"][c.chunk_id] for c in r.candidates} <= {
                        f"c{i:03d}" for i in range(FIXTURE_TERMS[term])
                    }

    def test_ties_break_by_chunk_id_and_repeated_runs_are_identical(self, db, seed):
        dsn = db["users"]["app"]
        first = self.search(dsn, "CO", "beta", 20)
        assert first.returned_count == 3
        # c001 and c002 have identical structure, so every ranking function ties them (ts_rank_cd ties all
        # three); equal scores must be ordered by chunk_id ascending
        scores = [c.raw_score for c in first.candidates]
        assert len(set(scores)) < 3
        for earlier, later in zip(first.candidates, first.candidates[1:], strict=False):
            assert later.raw_score < earlier.raw_score or (
                later.raw_score == earlier.raw_score and later.chunk_id > earlier.chunk_id
            )
        for _ in range(3):
            assert self.search(dsn, "CO", "beta", 20) == first

    def test_query_without_tokens_yields_zero_eligible_candidates(self, db, seed):
        r = self.search(db["users"]["app"], "MA", "!!!", 20)
        assert r.returned_count == 0 and r.candidate_exhausted is True

    def test_version_mismatch_is_refused_by_adapter_and_boundary(self, db, seed, tmp_path):
        with txn(db["users"]["app"], "MA") as conn:
            built = self.cut.expected_versions(conn)
            drifted = self.cut.drifted_versions(conn, tmp_path)
            assert drifted != built
            retriever = self.cut.make_drifted_retriever(conn, AS_OF, tmp_path)
            assert retriever.versions == built  # what the index was built with, not the drifted query config
            with pytest.raises(BusinessError) as exc:
                retriever.search("sigma", 20)
            assert exc.value.code is ErrorCode.version_conflict
            with pytest.raises(BusinessError) as exc2:
                run_lexical_search(retriever, "sigma", 20, expected=drifted)
            assert exc2.value.code is ErrorCode.version_conflict

    def test_explain_under_the_app_role_shows_the_policy_chain_and_filters(self, db, seed):
        with txn(db["users"]["app"], "MA") as conn:
            conn.execute("set local enable_seqscan = off")
            plan = self.cut.make_retriever(conn, AS_OF).explain("sigma 研究", 20)
        tree = json.loads(plan)
        assert tree and tree[0]["Plan"]["Node Type"] == "Limit"
        assert self.cut.index_table in plan and "document_acl" in plan
        assert "medops_current_dept" in plan or "current_setting('medops.dept'" in plan  # the SQL function is inlined
        assert "effective_from" in plan
        assert "'active'" in plan or "documents_one_active_per_family" in plan
        with txn(db["users"]["app"], "MA") as conn:
            conn.execute("set local enable_seqscan = off")
            conn.execute("set local enable_indexscan = off")
            gin_plan = self.cut.make_retriever(conn, AS_OF).explain("sigma 研究", 20)
        assert any(marker in gin_plan for marker in self.cut.index_plan_markers), gin_plan[:400]

    def test_app_and_readonly_roles_cannot_write_the_index(self, db, seed):
        some = next(iter(seed["eligible"]["MA"]))
        for kind in ("app", "readonly"):
            with psycopg.connect(db["users"][kind]) as conn:
                with pytest.raises(errors.InsufficientPrivilege):
                    conn.execute(f"delete from {self.cut.index_table} where chunk_id = %s", (some,))
                conn.rollback()
                with pytest.raises(errors.InsufficientPrivilege):
                    conn.execute(f"update {META_TABLE} set chunk_count = 0")
                conn.rollback()

    def test_rebuild_through_the_admin_login_user_replaces_the_index(self, db, seed):
        with psycopg.connect(db["users"]["admin"]) as conn:
            report = self.cut.build(conn, "test-admin-02")
            conn.commit()
            assert report.chunk_count == seed["report"].chunk_count
            row = conn.execute(
                f"select built_by, chunk_count from {META_TABLE} where index_name = %s", (report.index_name,)
            ).fetchone()
            assert row == ("test-admin-02", report.chunk_count)
