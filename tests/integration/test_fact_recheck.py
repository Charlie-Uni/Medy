"""M1-18: the fact-plane re-check under the real schema, real LOGIN users and FORCE RLS. Candidates the
department may not read, drafts and withdrawn documents are `not_visible`; visible rows are judged on
status, effective window, source integrity, parse quality, content hash and page offsets; the check
refuses to run on a connection that is not subject to the ACL policies; and chained after candidate A
it drops what the lexical index (which filters status and window only) still returned.

Own temporary database: the seeds leave active documents behind (non-draft documents cannot be deleted)."""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterator
from datetime import date

import psycopg
import pytest

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.retrieval.lexical import pg_simple_fts as a
from medops.retrieval.lexical.boundary import run_lexical_search
from medops.retrieval.recheck import RejectReason, recheck_candidates
from tests.integration.lexical_adapter_suite import make_database, txn
from tests.integration.test_migrations import document, job, source_object

pytest.importorskip("jieba")
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1  # noqa: E402

TOKENIZER = JiebaTokenizerV1()
AS_OF = date(2026, 6, 1)
WORD = "kappa"  # present in every seeded chunk so one lexical query returns them all


@pytest.fixture(scope="module")
def db(admin_dsn: str) -> Iterator[dict]:
    yield from make_database(admin_dsn)


@pytest.fixture(scope="module")
def seed(db: dict) -> dict:
    """One chunk per case; `cases[name] = chunk_id`. Sources are verified unless the case says otherwise."""
    cases: dict[str, str] = {}
    counter = 7000
    with psycopg.connect(db["owner"]) as conn:
        a.install(conn)

        def make(
            name,
            *,
            dept="MA",
            acl=("MA",),
            status="active",
            quality="trusted",
            integrity="verified",
            effective_from=date(2026, 1, 1),
            effective_to=None,
            spans=True,
            section="用法用量",
        ):
            nonlocal counter
            counter += 1
            src = source_object(conn, counter)
            conn.execute(
                "update source_objects set integrity_status = %s, last_verified_at = case when %s = 'verified' then now() end "
                "where source_object_id = %s",
                (integrity, integrity, src),
            )
            if status == "draft":
                doc = document(conn, src, None, family_id=uuid.uuid4(), owner_dept=dept, version=f"v{counter}")
            else:
                doc = document(
                    conn,
                    src,
                    job(conn, src, quality=quality),
                    family_id=uuid.uuid4(),
                    owner_dept=dept,
                    version=f"v{counter}",
                    status=status,
                    parse_quality=quality,
                    effective_from=effective_from,
                    effective_to=effective_to,
                )
            for d in acl:
                conn.execute(
                    "insert into document_acl (doc_id, dept, granted_by) values (%s, %s, 'admin-01')", (doc, d)
                )
            text = f"{WORD} {name} 每次 0.5 g，每日 2 次。"
            cid = conn.execute(
                "insert into chunks (doc_id, seq, page, section, content, chunk_content_hash) values (%s, 0, 2, %s, %s, null) returning chunk_id",
                (doc, section, text),
            ).fetchone()[0]
            if spans:
                conn.execute(
                    "insert into chunk_spans (chunk_id, ordinal, page, char_start, char_end) values (%s, 0, 2, 0, %s)",
                    (cid, len(text)),
                )
            cases[name] = str(cid)
            return cid

        make("good")
        make("good2")
        make("integrity_pending", integrity="pending")
        make("integrity_failed", integrity="failed")
        make("future", effective_from=AS_OF.replace(day=2))
        make("expired", effective_to=AS_OF)
        make("archived", status="archived", effective_from=date(2025, 1, 1), effective_to=date(2026, 1, 1))
        make(
            "archived_low_trust",
            status="archived",
            quality="low_trust",
            effective_from=date(2025, 1, 1),
            effective_to=date(2026, 1, 1),
        )
        make("draft", status="draft")
        make("pv_only", dept="PV", acl=("PV",))
        make("shared", acl=("MA", "PV"))
        make("no_offsets", spans=False)
        tampered = make("tampered")
        # Simulate silent corruption of stored content: bypass the immutability trigger as the owner.
        conn.execute("set session_replication_role = replica")
        conn.execute("update chunks set content = content || ' 篡改' where chunk_id = %s", (tampered,))
        conn.execute("set session_replication_role = default")
        conn.commit()
    with psycopg.connect(db["users"]["admin"]) as conn:
        a.build_index(conn, TOKENIZER, built_by="test-admin-01")
        conn.commit()
    return cases


def _reasons(result) -> dict[str, str]:
    return {r.chunk_id: r.reason.value for r in result.rejected}


@pytest.mark.parametrize("kind", ["app", "readonly"])
def test_every_case_is_accepted_or_rejected_with_exactly_its_reason(db, seed, kind):
    unknown = str(uuid.uuid4())
    order = [
        "tampered",
        "good",
        "draft",
        "pv_only",
        "expired",
        "good2",
        "future",
        "integrity_pending",
        "archived",
        "shared",
        "no_offsets",
        "integrity_failed",
        "archived_low_trust",
    ]
    ids = [seed[n] for n in order] + [unknown, seed["good"]]
    with txn(db["users"][kind], "MA") as conn:
        result = recheck_candidates(conn, ids, as_of=AS_OF)
    assert result.accepted_ids == (seed["good"], seed["good2"], seed["shared"])  # input (rank) order kept
    non_duplicate = {r.chunk_id: r.reason.value for r in result.rejected if r.reason is not RejectReason.duplicate}
    assert non_duplicate == {
        seed["tampered"]: "content_hash_mismatch",
        seed["draft"]: "not_visible",
        seed["pv_only"]: "not_visible",
        seed["expired"]: "expired",
        seed["future"]: "not_yet_effective",
        seed["integrity_pending"]: "source_integrity_not_verified",
        seed["integrity_failed"]: "source_integrity_not_verified",
        seed["archived"]: "status_not_active",
        seed["no_offsets"]: "no_source_offsets",
        seed["archived_low_trust"]: "status_not_active",
        unknown: "not_visible",
    }
    duplicate = [r for r in result.rejected if r.reason is RejectReason.duplicate]
    assert [(r.chunk_id, r.rank) for r in duplicate] == [(seed["good"], len(ids))]
    tampered = next(r for r in result.rejected if r.chunk_id == seed["tampered"])
    assert tampered.expected_hash != tampered.observed_hash and tampered.rank == 1
    assert all(r.expected_hash is None and r.observed_hash is None for r in result.rejected if r is not tampered)
    good = result.evidence[0]
    assert (
        good.citation.page == 2
        and good.citation.section == "用法用量"
        and good.citation.effective_date == date(2026, 1, 1)
    )
    assert good.evidence_text_hash == hashlib.sha256(good.text.encode("utf-8")).hexdigest() == good.chunk_content_hash
    assert good.status.value == "active" and good.historical is False


def test_cross_department_candidates_are_invisible_and_leak_nothing(db, seed):
    with txn(db["users"]["app"], "PV") as conn:
        result = recheck_candidates(conn, [seed["good"], seed["pv_only"], seed["shared"]], as_of=AS_OF)
    assert result.accepted_ids == (seed["pv_only"], seed["shared"])
    (denied,) = result.rejected
    assert denied.model_dump() == {
        "chunk_id": seed["good"],
        "rank": 1,
        "reason": "not_visible",
        "expected_hash": None,
        "observed_hash": None,
    }
    with txn(db["users"]["app"], "CO") as conn:
        result = recheck_candidates(conn, [seed["good"], seed["pv_only"], seed["shared"]], as_of=AS_OF)
    assert result.evidence == () and set(_reasons(result).values()) == {"not_visible"}


def test_historical_evidence_needs_explicit_as_of_and_is_marked_historical(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        with pytest.raises(BusinessError) as exc:
            recheck_candidates(conn, [seed["archived"]], allow_historical=True)
        assert exc.value.code is ErrorCode.invalid_request
        result = recheck_candidates(
            conn,
            [seed["archived"], seed["archived_low_trust"], seed["good"], seed["draft"]],
            as_of=date(2025, 6, 1),
            allow_historical=True,
        )
        assert result.accepted_ids == (seed["archived"],)
        assert result.evidence[0].historical is True and result.evidence[0].status.value == "archived"
        assert _reasons(result) == {
            seed["archived_low_trust"]: "parse_quality_not_trusted",
            seed["good"]: "not_yet_effective",  # active since 2026-01-01, not at 2025-06-01
            seed["draft"]: "not_visible",  # historical mode widens nothing about visibility
        }
        later = recheck_candidates(conn, [seed["archived"]], as_of=AS_OF, allow_historical=True)
        assert _reasons(later) == {seed["archived"]: "expired"}


def test_missing_identity_or_transaction_is_refused_not_empty(db, seed):
    with txn(db["users"]["app"], None) as conn:
        with pytest.raises(BusinessError) as exc:
            recheck_candidates(conn, [seed["good"]], as_of=AS_OF)
        assert exc.value.code is ErrorCode.unauthenticated
    with psycopg.connect(db["users"]["app"], autocommit=True) as conn:
        conn.execute("select set_config('medops.dept', 'MA', false)")
        with pytest.raises(BusinessError) as exc:
            recheck_candidates(conn, [seed["good"]], as_of=AS_OF)
        assert exc.value.code is ErrorCode.unauthenticated


@pytest.mark.parametrize("kind", ["admin", "owner"])
def test_roles_not_subject_to_the_acl_policies_are_refused(db, seed, kind):
    dsn = db["owner"] if kind == "owner" else db["users"]["admin"]
    with txn(dsn, "MA") as conn:
        with pytest.raises(InfrastructureError) as exc:
            recheck_candidates(conn, [seed["good"]], as_of=AS_OF)
        assert exc.value.code is ErrorCode.internal_error and exc.value.retryable is False


def test_adapter_defects_fail_closed_and_an_empty_input_is_an_empty_result(db, seed):
    with txn(db["users"]["app"], "MA") as conn:
        for bad in ("not-a-uuid", 42, None):
            with pytest.raises(InfrastructureError):
                recheck_candidates(conn, [seed["good"], bad], as_of=AS_OF)  # type: ignore[list-item]
        empty = recheck_candidates(conn, [], as_of=AS_OF)
        assert empty.evidence == () and empty.rejected == () and empty.as_of == AS_OF


def test_chained_after_candidate_a_the_recheck_drops_what_the_index_still_returns(db, seed):
    """The lexical SQL filters status and the effective window; it does not know about source integrity,
    tampered content or missing offsets. Those still come back as candidates and the re-check stops them."""
    with txn(db["users"]["app"], "MA") as conn:
        retriever = a.PgSimpleFtsRetriever(conn, TOKENIZER, as_of=AS_OF)
        hits = run_lexical_search(retriever, WORD, 20, expected=retriever.versions)
        returned = [c.chunk_id for c in hits.candidates]
        result = recheck_candidates(conn, returned, as_of=AS_OF)
    assert set(returned) == {
        seed[n] for n in ("good", "good2", "shared", "integrity_pending", "integrity_failed", "no_offsets", "tampered")
    }
    assert set(result.accepted_ids) == {seed["good"], seed["good2"], seed["shared"]}
    assert result.accepted_ids == tuple(c for c in returned if c in result.accepted_ids)  # rank order preserved
    assert set(_reasons(result).values()) == {
        "source_integrity_not_verified",
        "no_source_offsets",
        "content_hash_mismatch",
    }
