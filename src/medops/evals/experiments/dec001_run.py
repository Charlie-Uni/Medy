"""DEC-001 comparison runner (ADR-0002, experiment_plan.json `measurement`).

One run = a frozen `run_manifest.json` written BEFORE any query, then every candidate executed over the
same 75 frozen queries with the same K, the same per-pass query order (sorted sample_id, shuffled with
seed + pass_index), concurrency 1, `warmup_full_passes` unmeasured passes and `measured_full_passes`
measured passes, on ordinary-role connections bound to the sample's department per transaction.

Per query and candidate the runner records the ranked chunk ids of every execution (they must be
identical, otherwise the reproducibility gate fails), the latency of each measured execution
(perf_counter_ns around tokenizer + database roundtrip), `returned_count` / `candidate_exhausted`, the
strict recall against the candidate server's own gold->chunk mapping, and an admin-side check that no
returned chunk belongs to a document outside the department's ACL or outside `active`.

The runner never edits samples, mappings or indexes; it refuses to write into an existing output
directory. Gates and selection arithmetic live in `scoring` and `evaluate`; nothing here interprets the
result as a production decision.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import random
import subprocess
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlsplit, urlunsplit

import psycopg

from medops.core.canonical import canonical_json
from medops.evals.experiments import scoring
from medops.retrieval.contracts import LexicalSearchResult, LexicalVersions
from medops.retrieval.lexical import pg_search_bm25, pg_simple_fts, pg_zhparser_fts
from medops.retrieval.lexical.boundary import run_lexical_search

SLICES = ("drug_name_zh", "dose_unit", "negation", "time_window", "protocol_id", "mixed_zh_en")
MIN_SLICE_SUPPORT = 8
CANDIDATES = ("A", "A2", "B", "B2", "C", "D")  # A2/B2: amendment 2 stopword variants; D: revision 5 (pg_textsearch)
STOPWORDS = Path("evals/experiments/lexical/resources/english.stop")

# ------------------------------------------------------------------------------- inputs


LANGUAGE_MATCHED = "language_matched"
CROSS_LINGUAL = "cross_lingual"


def gate_scope(language: str, gold_script: str) -> str:
    """ADR-0002 amendment 1: gold en + query en, or gold zh + query zh/mixed -> language_matched;
    gold en + Chinese query -> cross_lingual (reported, not gated)."""
    if gold_script == "en":
        return LANGUAGE_MATCHED if language == "en" else CROSS_LINGUAL
    return LANGUAGE_MATCHED


@dataclass(frozen=True)
class Query:
    sample_id: str
    dept: str
    query: str
    slices: tuple[str, ...]
    gold_ids: tuple[str, ...]
    gold_script: str  # language of the gold document (zh-Hans / zh-Hant / en / mixed)
    language: str = "zh"
    derived_from: str | None = None
    provisional: bool = False  # unreviewed/unconfirmed twin overlay: reported separately, never a gate input

    @property
    def scope(self) -> str:
        return gate_scope(self.language, self.gold_script)


def load_queries(dataset_dir: Path) -> list[Query]:
    corpus = json.loads((dataset_dir / "corpus.json").read_text(encoding="utf-8"))
    language_by_hash = {d["source_hash"]: d["language"] for d in corpus["documents"]}
    queries = []
    for line in (dataset_dir / "samples.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        s = json.loads(line)
        golds = s["required_gold_evidence"]
        scripts = {language_by_hash[g["source_hash"]] for g in golds}
        queries.append(
            Query(
                sample_id=s["sample_id"],
                dept=s["dept"],
                query=s["query"],
                slices=tuple(s["slices"]),
                gold_ids=tuple(g["gold_id"] for g in golds),
                gold_script="+".join(sorted(scripts)),
                language=s.get("language", "zh"),
                derived_from=s.get("derived_from"),
            )
        )
    return sorted(queries, key=lambda q: q.sample_id)


def load_twin_overlay(path: Path, base: Sequence[Query]) -> list[Query]:
    """Provisional English twins (drafts/v2/samples_draft_EN.json) evaluated against the PARENT's golds:
    they are not part of the frozen dataset, carry `provisional=True`, and are reported separately."""
    by_id = {q.sample_id: q for q in base}
    twins = []
    for t in json.loads(path.read_text(encoding="utf-8")):
        parent = by_id[t["derived_from"]]
        twins.append(
            Query(
                sample_id=t["sample_id"],
                dept=t["dept"],
                query=t["query"],
                slices=tuple(t["slices"]),
                gold_ids=parent.gold_ids,
                gold_script=parent.gold_script,
                language=t.get("language", "en"),
                derived_from=t["derived_from"],
                provisional=True,
            )
        )
    return twins


def load_mapping(path: Path) -> dict[str, list[str]]:
    """gold_id -> mapped chunk ids (empty list = unmappable, always a miss)."""
    mapping = json.loads(path.read_text(encoding="utf-8"))
    return {e["gold_id"]: list(e["chunk_ids"]) if e["status"] == "mapped" else [] for e in mapping["entries"]}


# ------------------------------------------------------------------------------- servers


@dataclass(frozen=True)
class CandidateServer:
    candidate: str
    app_dsn: str
    admin_dsn: str
    mapping_path: Path
    image_local_id: str | None = None


def _with_database(url: str, name: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))


def _with_user(url: str, user: str, password: str) -> str:
    parts = urlsplit(url)
    hostport = (parts.hostname or "localhost") + (f":{parts.port}" if parts.port else "")
    return urlunsplit(
        (
            parts.scheme,
            f"{quote(user, safe='')}:{quote(password, safe='')}@{hostport}",
            parts.path,
            parts.query,
            parts.fragment,
        )
    )


def resolve_servers(repo: Path, mappings: Mapping[str, Path], plan: Mapping[str, Any]) -> dict[str, CandidateServer]:
    """A from `.env` (DATABASE_URL = app user, DATABASE_ADMIN_URL), B/C from the gitignored `.env.dec001`
    superuser URLs with the app user's password from `.env`."""
    from medops.core.config import Settings

    settings = Settings(_env_file=repo / ".env")  # type: ignore[call-arg]
    app_password = settings.db_app_password.get_secret_value() if settings.db_app_password else ""
    images = {c["id"]: c.get("image_local_id") for c in plan["candidates"]}
    images.setdefault("A2", images.get("A"))
    images.setdefault("B2", images.get("B"))
    servers = {
        "A": CandidateServer(
            "A",
            settings.database_url.get_secret_value(),
            (settings.database_admin_url or settings.database_url).get_secret_value(),
            mappings["A"],
            images.get("A"),
        )
    }
    env = {}
    dec = repo / ".env.dec001"
    if dec.is_file():
        for line in dec.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                env[key.strip()] = value.strip()
    for cand in ("B", "C", "D"):
        admin = os.environ.get(f"DEC001_{cand}_ADMIN_URL") or env.get(f"DEC001_{cand}_ADMIN_URL")
        if admin and cand in mappings:
            servers[cand] = CandidateServer(
                cand, _with_user(admin, "medops_app_user", app_password), admin, mappings[cand], images.get(cand)
            )
    # variants live on the same server and database as their base candidate (own index table)
    for variant, base in (("A2", "A"), ("B2", "B")):
        if base in servers and variant in mappings:
            b = servers[base]
            servers[variant] = CandidateServer(variant, b.app_dsn, b.admin_dsn, mappings[variant], b.image_local_id)
    return servers


_TOKENIZERS: dict[str, Any] = {}


def _jieba_tokenizer() -> Any:
    """One tokenizer instance per process: loading jieba's dictionary costs ~200 ms and belongs to
    process start-up, not to a query's latency (production keeps the instance alive)."""
    if "A" not in _TOKENIZERS:
        from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1

        _TOKENIZERS["A"] = JiebaTokenizerV1()
    return _TOKENIZERS["A"]


def _jieba_v2_tokenizer() -> Any:
    if "A2" not in _TOKENIZERS:
        from medops.retrieval.lexical.tokenizer import JiebaTokenizerV2

        _TOKENIZERS["A2"] = JiebaTokenizerV2(stopwords=STOPWORDS)
    return _TOKENIZERS["A2"]


def make_retriever(candidate: str, conn: psycopg.Connection[Any], as_of: date) -> Any:
    if candidate == "A":
        return pg_simple_fts.PgSimpleFtsRetriever(conn, _jieba_tokenizer(), as_of=as_of)
    if candidate == "A2":
        return pg_simple_fts.PgSimpleFtsRetriever(
            conn, _jieba_v2_tokenizer(), as_of=as_of, index_name="a2", table="lexical_index_a2"
        )
    if candidate == "B":
        return pg_zhparser_fts.PgZhparserFtsRetriever(conn, as_of=as_of)
    if candidate == "B2":
        return pg_zhparser_fts.PgZhparserFtsRetriever(conn, as_of=as_of, variant=pg_zhparser_fts.VARIANT_B2)
    if candidate == "C":
        return pg_search_bm25.PgSearchBm25Retriever(conn, as_of=as_of)
    if candidate == "D":  # revision 5: A2's tokens, BM25 ranking
        from medops.retrieval.lexical import pg_textsearch_bm25

        return pg_textsearch_bm25.PgTextsearchBm25Retriever(conn, _jieba_v2_tokenizer(), as_of=as_of)
    raise ValueError(candidate)


# ------------------------------------------------------------------------------- manifest


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_head(repo: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def server_facts(admin_dsn: str, candidate: str) -> dict[str, Any]:
    """Read-only facts for the manifest: server version, extensions, built index versions, document states."""
    index_name = {"A": "a", "A2": "a2", "B": "b", "B2": "b2", "C": "c", "D": "d"}[candidate]
    with psycopg.connect(admin_dsn) as conn:
        with conn.transaction():
            conn.execute("set transaction read only")
            version = conn.execute("show server_version").fetchone()
            exts = conn.execute(
                "select extname, extversion from pg_extension where extname in ('vector','zhparser','pg_search','pg_textsearch') order by 1"
            ).fetchall()
            meta = conn.execute(
                "select retriever_version, tokenizer_version, dictionary_version, normalization_version, chunk_count, built_by, built_at "
                "from lexical_index_meta where index_name = %s",
                (index_name,),
            ).fetchone()
            docs = conn.execute(
                "select status::text, parse_quality::text, count(*) from documents group by 1, 2 order by 1, 2"
            ).fetchall()
            chunks = conn.execute("select count(*) from chunks").fetchone()
            migration = conn.execute("select version_num from alembic_version").fetchone()
    if meta is None:
        raise RuntimeError(
            f"candidate {candidate}: lexical index '{index_name}' is not built on {urlsplit(admin_dsn).hostname}"
        )
    return {
        "postgresql": version[0] if version else None,
        "migration": migration[0] if migration else None,
        "extensions": {name: ver for name, ver in exts},
        "index": {
            "retriever_version": meta[0],
            "tokenizer_version": meta[1],
            "dictionary_version": meta[2],
            "normalization_version": meta[3],
            "chunk_count": meta[4],
            "built_by": meta[5],
            "built_at": meta[6].isoformat(),
        },
        "documents_by_status_quality": [{"status": s, "parse_quality": q, "count": n} for s, q, n in docs],
        "chunks": chunks[0] if chunks else None,
    }


def build_manifest(
    *,
    run_id: str,
    repo: Path,
    dataset_dir: Path,
    plan: Mapping[str, Any],
    servers: Mapping[str, CandidateServer],
    as_of: date,
    k: int,
    warmup: int,
    measured: int,
    seed: int,
    purpose: str,
) -> dict[str, Any]:
    manifest = json.loads((dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "frozen":
        raise RuntimeError("dataset is not frozen")
    candidates = {}
    for cand, server in sorted(servers.items()):
        mapping = json.loads(server.mapping_path.read_text(encoding="utf-8"))
        if mapping["dataset_hash"] != manifest["dataset_hash"]:
            raise RuntimeError(f"candidate {cand}: mapping dataset_hash differs from the frozen dataset")
        statuses = [e["status"] for e in mapping["entries"]]
        candidates[cand] = {
            "server": f"{urlsplit(server.admin_dsn).hostname or 'localhost'}:{urlsplit(server.admin_dsn).port or 5432}",
            "app_role_user": urlsplit(server.app_dsn).username,
            "image_local_id": server.image_local_id,
            "mapping_file": str(server.mapping_path.relative_to(repo)),
            "mapping_sha256": _sha256(server.mapping_path),
            "mapping_counts": {"mapped": statuses.count("mapped"), "unmappable": statuses.count("unmappable")},
            **server_facts(server.admin_dsn, cand),
        }
    return {
        "run_id": run_id,
        "status": "frozen_before_run",
        "purpose": purpose,
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "git_head": _git_head(repo),
        "protocol": "docs/adr/ADR-0002-lexical-retrieval-selection.md",
        "experiment_plan_sha256": _sha256(repo / "evals/experiments/lexical/preparation-v1/experiment_plan.json"),
        "dataset": {
            "version": manifest["dataset_version"],
            "dataset_hash": manifest["dataset_hash"],
            "manifest_sha256": _sha256(dataset_dir / "manifest.json"),
            "samples_sha256": _sha256(dataset_dir / "samples.jsonl"),
        },
        "measurement": {
            "k": k,
            "as_of": as_of.isoformat(),
            "query_order": "sorted sample_id, shuffled per pass with random.Random(seed + pass_index)",
            "random_seed": seed,
            "concurrency": 1,
            "warmup_full_passes": warmup,
            "measured_full_passes": measured,
            "latency_clock": "perf_counter_ns around run_lexical_search (tokenizer + database roundtrip)",
            "p95_estimator": "nearest-rank ceil(0.95*n), warmup excluded",
            "paired_bootstrap": {
                "resamples": plan["measurement"]["paired_bootstrap_resamples"],
                "seed": plan["measurement"]["paired_bootstrap_seed"],
                "confidence_level": plan["measurement"]["confidence_level"],
            },
            "tie_break": "chunk_id ascending",
            "min_slice_support": MIN_SLICE_SUPPORT,
        },
        "environment": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count(),
            "python": platform.python_version(),
        },
        "candidates": candidates,
    }


# ------------------------------------------------------------------------------- execution


@dataclass
class QueryOutcome:
    sample_id: str
    dept: str
    rankings: list[list[str]] = field(default_factory=list)
    latencies_ns: list[int] = field(default_factory=list)  # measured passes only
    returned_count: int | None = None
    candidate_exhausted: bool | None = None


class SearchOutcome(Protocol):
    """What the pass executor reads from any retriever result (lexical or vector)."""

    @property
    def candidates(self) -> Sequence[Any]: ...

    @property
    def returned_count(self) -> int: ...

    @property
    def candidate_exhausted(self) -> bool: ...


Searcher = Callable[[Query, int], SearchOutcome]


def execute_passes(
    queries: Sequence[Query], search: Searcher, *, k: int, warmup: int, measured: int, seed: int
) -> dict[str, QueryOutcome]:
    outcomes = {q.sample_id: QueryOutcome(q.sample_id, q.dept) for q in queries}
    by_id = {q.sample_id: q for q in queries}
    ids = sorted(by_id)
    for pass_index in range(warmup + measured):
        order = list(ids)
        random.Random(seed + pass_index).shuffle(order)
        for sid in order:
            q = by_id[sid]
            start = time.perf_counter_ns()
            result = search(q, k)
            elapsed = time.perf_counter_ns() - start
            out = outcomes[sid]
            out.rankings.append([c.chunk_id for c in result.candidates])
            if pass_index >= warmup:
                out.latencies_ns.append(elapsed)
            out.returned_count = result.returned_count
            out.candidate_exhausted = result.candidate_exhausted
    return outcomes


def db_searcher(server: CandidateServer, as_of: date, k_expected_versions: LexicalVersions | None = None):
    """A searcher over ONE ordinary-role connection (pool-reuse semantics): each query runs in its own
    transaction with the sample's department injected via set_config(..., true)."""
    conn = psycopg.connect(server.app_dsn)
    expected: dict[str, LexicalVersions] = {}

    def search(q: Query, k: int) -> LexicalSearchResult:
        with conn.transaction():
            conn.execute("select set_config('medops.dept', %s, true)", (q.dept,))
            retriever = make_retriever(server.candidate, conn, as_of)
            if "v" not in expected:
                expected["v"] = retriever.configured  # fixed once per run from the run configuration
            return run_lexical_search(retriever, q.query, k, expected=expected["v"])

    search.close = conn.close  # type: ignore[attr-defined]
    return search


def leak_check(admin_dsn: str, outcomes: Mapping[str, QueryOutcome], as_of: date) -> list[dict[str, Any]]:
    """Admin-side verification: every returned chunk belongs to an ACTIVE, effective document with a read
    ACL for the query's department. Returns the violations (expected: none)."""
    violations = []
    with psycopg.connect(admin_dsn) as conn:
        for sid, out in sorted(outcomes.items()):
            if not out.rankings or not out.rankings[0]:
                continue
            rows = conn.execute(
                """select c.chunk_id from chunks c join documents d using (doc_id)
                   where c.chunk_id = any(%s::uuid[])
                     and not (d.status = 'active' and d.effective_from <= %s
                              and (d.effective_to is null or d.effective_to > %s)
                              and exists (select 1 from document_acl a where a.doc_id = d.doc_id
                                          and a.permission = 'read' and a.dept = %s))""",
                (out.rankings[0], as_of, as_of, out.dept),
            ).fetchall()
            for (chunk_id,) in rows:
                violations.append({"sample_id": sid, "dept": out.dept, "chunk_id": str(chunk_id)})
    return violations


# ------------------------------------------------------------------------------- aggregation


def _labels_script(subset: Sequence[Query]) -> dict[str, list[str]]:
    labels: dict[str, list[str]] = {}
    for q in subset:
        labels.setdefault(q.gold_script, []).append(q.sample_id)
    return labels


def summarize(
    candidate: str, queries: Sequence[Query], outcomes: Mapping[str, QueryOutcome], mapping: Mapping[str, list[str]]
) -> dict[str, Any]:
    per_query: dict[str, float] = {}
    rows = []
    not_reproducible = []
    for q in queries:
        out = outcomes[q.sample_id]
        required = ["|".join(mapping.get(g, [])) for g in q.gold_ids]
        recall = scoring.strict_recall(out.rankings[0], required)
        per_query[q.sample_id] = recall
        if not scoring.rankings_identical(out.rankings):
            not_reproducible.append(q.sample_id)
        ranks = {}
        for g in q.gold_ids:
            hit_rank = next((i + 1 for i, cid in enumerate(out.rankings[0]) if cid in set(mapping.get(g, []))), None)
            ranks[g] = hit_rank
        rows.append(
            {
                "sample_id": q.sample_id,
                "dept": q.dept,
                "slices": list(q.slices),
                "gold_script": q.gold_script,
                "language": q.language,
                "scope": q.scope,
                "provisional": q.provisional,
                "derived_from": q.derived_from,
                "recall": recall,
                "gold_ranks": ranks,
                "returned_count": out.returned_count,
                "candidate_exhausted": out.candidate_exhausted,
                "latency_ms_measured": [round(ns / 1e6, 3) for ns in out.latencies_ns],
                "unmappable_golds": [g for g in q.gold_ids if not mapping.get(g)],
            }
        )
    labels_dept = {d: [q.sample_id for q in queries if q.dept == d] for d in ("MA", "PV", "CO")}
    labels_slice = {s: [q.sample_id for q in queries if s in q.slices] for s in SLICES}
    labels_script: dict[str, list[str]] = {}
    for q in queries:
        labels_script.setdefault(q.gold_script, []).append(q.sample_id)
    labels_drug_script: dict[str, list[str]] = {
        f"drug_name_zh/{q.gold_script}": [] for q in queries if "drug_name_zh" in q.slices
    }
    for q in queries:
        if "drug_name_zh" in q.slices:
            labels_drug_script[f"drug_name_zh/{q.gold_script}"].append(q.sample_id)
    latencies = [ns / 1e6 for out in outcomes.values() for ns in out.latencies_ns]

    def group(labels: Mapping[str, Sequence[str]]) -> list[dict[str, Any]]:
        return [g.__dict__ for g in scoring.grouped_recall(per_query, labels, min_support=MIN_SLICE_SUPPORT)]

    def group_block(subset: Sequence[Query]) -> dict[str, Any]:
        ids_ = [q.sample_id for q in subset]
        return {
            "queries": len(subset),
            "strict_macro_recall": scoring.macro_mean([per_query[i] for i in ids_]),
            "by_department": group({d: [q.sample_id for q in subset if q.dept == d] for d in ("MA", "PV", "CO")}),
            "by_slice": group({sl: [q.sample_id for q in subset if sl in q.slices] for sl in SLICES}),
            "by_gold_script": group(_labels_script(subset)),
            "sample_ids": ids_,
        }

    frozen = [q for q in queries if not q.provisional]
    matched = [q for q in frozen if q.scope == LANGUAGE_MATCHED]
    cross = [q for q in frozen if q.scope == CROSS_LINGUAL]
    provisional = [q for q in queries if q.provisional]

    return {
        "candidate": candidate,
        "queries": len(queries),
        "strict_macro_recall": scoring.macro_mean([per_query[q.sample_id] for q in frozen]),
        "scopes": {
            LANGUAGE_MATCHED: group_block(matched),
            CROSS_LINGUAL: group_block(cross),
            "provisional_twins": group_block(provisional),
            "language_matched_plus_provisional_twins": group_block(matched + provisional),
        },
        "by_department": group(labels_dept),
        "by_slice": group(labels_slice),
        "by_gold_script": group(labels_script),
        "drug_name_zh_by_script": group(labels_drug_script),
        "candidate_exhausted_queries": sum(1 for o in outcomes.values() if o.candidate_exhausted),
        "zero_result_queries": sum(1 for o in outcomes.values() if o.returned_count == 0),
        "not_reproducible_queries": not_reproducible,
        "latency_ms": {
            "measured_executions": len(latencies),
            "p95": scoring.p95_nearest_rank(latencies) if latencies else None,
            "mean": scoring.macro_mean(latencies),
            "max": max(latencies) if latencies else None,
        },
        "per_query": rows,
        "_per_query_recall": per_query,
    }


# ------------------------------------------------------------------------------- orchestration


def run(
    *,
    repo: Path,
    dataset_dir: Path,
    out_dir: Path,
    servers: Mapping[str, CandidateServer],
    plan: Mapping[str, Any],
    as_of: date,
    k: int,
    warmup: int,
    measured: int,
    seed: int,
    purpose: str,
    searcher_factory: Callable[[CandidateServer], Any] | None = None,
    leak_checker: Callable[[CandidateServer, Mapping[str, QueryOutcome]], list[dict[str, Any]]] | None = None,
    twins_path: Path | None = None,
) -> dict[str, Any]:
    if out_dir.exists():
        raise FileExistsError(f"refusing to overwrite an existing run directory: {out_dir}")
    queries = load_queries(dataset_dir)
    if twins_path is not None:
        queries = sorted(queries + load_twin_overlay(twins_path, queries), key=lambda q: q.sample_id)
    run_id = out_dir.name
    manifest = build_manifest(
        run_id=run_id,
        repo=repo,
        dataset_dir=dataset_dir,
        plan=plan,
        servers=servers,
        as_of=as_of,
        k=k,
        warmup=warmup,
        measured=measured,
        seed=seed,
        purpose=purpose,
    )
    if twins_path is not None:
        manifest["provisional_twin_overlay"] = {
            "file": str(twins_path.relative_to(repo)) if twins_path.is_relative_to(repo) else str(twins_path),
            "sha256": _sha256(twins_path),
            "count": sum(1 for q in queries if q.provisional),
            "status": "unreviewed and unconfirmed: reported separately, never a gate input",
        }
    manifest["gate_scope_rule"] = (
        "ADR-0002 amendment 1: hard gates on language_matched frozen samples; cross_lingual reported separately"
    )
    out_dir.mkdir(parents=True)
    manifest_bytes = (canonical_json(manifest) + "\n").encode("utf-8")
    (out_dir / "run_manifest.json").write_bytes(manifest_bytes)
    results: dict[str, Any] = {
        "run_id": run_id,
        "run_manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        "started_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "candidates": {},
    }
    per_query_by_candidate: dict[str, dict[str, float]] = {}
    gate_ids = {q.sample_id for q in queries if not q.provisional and q.scope == LANGUAGE_MATCHED}
    for cand, server in sorted(servers.items()):
        mapping = load_mapping(server.mapping_path)
        search = searcher_factory(server) if searcher_factory else db_searcher(server, as_of)
        try:
            outcomes = execute_passes(queries, search, k=k, warmup=warmup, measured=measured, seed=seed)
        finally:
            close = getattr(search, "close", None)
            if close:
                close()
        summary = summarize(cand, queries, outcomes, mapping)
        per_query_by_candidate[cand] = {k: v for k, v in summary.pop("_per_query_recall").items() if k in gate_ids}
        summary["leak_violations"] = (
            leak_checker(server, outcomes) if leak_checker else leak_check(server.admin_dsn, outcomes, as_of)
        )
        results["candidates"][cand] = summary
    results["paired_against_A"] = {}
    results["paired_scope"] = LANGUAGE_MATCHED
    if "A" in per_query_by_candidate:
        boot = manifest["measurement"]["paired_bootstrap"]
        for cand in sorted(per_query_by_candidate):
            if cand == "A":
                continue
            diff = scoring.paired_bootstrap_difference(
                per_query_by_candidate["A"],
                per_query_by_candidate[cand],
                resamples=boot["resamples"],
                seed=boot["seed"],
                level=boot["confidence_level"],
            )
            results["paired_against_A"][cand] = diff.__dict__
    results["finished_at"] = dt.datetime.now(dt.UTC).isoformat(timespec="seconds")
    (out_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return results


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DEC-001 lexical comparison run (frozen manifest first)")
    parser.add_argument("--dataset", type=Path, default=Path("evals/probe/precise_clause/v1"))
    parser.add_argument("--out", type=Path, required=True, help="new run directory (must not exist)")
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--measured", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260920)
    parser.add_argument(
        "--candidates", default="A,B,C", help="e.g. A,A2,B,B2,C (A2/B2 = amendment 2 stopword variants)"
    )
    parser.add_argument(
        "--mapping-a", type=Path, default=Path("evals/experiments/lexical/preparation-v1/chunk_mapping.chunker-v1.json")
    )
    parser.add_argument(
        "--mapping-b",
        type=Path,
        default=Path("evals/experiments/lexical/preparation-v1/servers/b/chunk_mapping.chunker-v1.json"),
    )
    parser.add_argument(
        "--mapping-c",
        type=Path,
        default=Path("evals/experiments/lexical/preparation-v1/servers/c/chunk_mapping.chunker-v1.json"),
    )
    parser.add_argument(
        "--mapping-d",
        type=Path,
        default=Path("evals/experiments/e2e/main-v3-provisional/chunk_mapping.chunker-v2.main-v3-provisional.json"),
        help="candidate D holds a restored copy of medops_v2 (same chunk ids), so the main-set mapping applies",
    )
    parser.add_argument(
        "--purpose", required=True, help="e.g. 'pipeline smoke (all documents draft)' or 'M1-05 comparison'"
    )
    parser.add_argument("--twins", type=Path, default=None, help="provisional English twin overlay JSON")
    parser.add_argument("--database", default=None, help="database name to use on every server")
    args = parser.parse_args(argv)
    repo = Path.cwd()
    plan = json.loads(
        (repo / "evals/experiments/lexical/preparation-v1/experiment_plan.json").read_text(encoding="utf-8")
    )
    wanted = [c.strip() for c in args.candidates.split(",") if c.strip()]
    mappings = {"A": args.mapping_a.resolve(), "B": args.mapping_b.resolve(), "C": args.mapping_c.resolve()}
    mappings["A2"], mappings["B2"] = mappings["A"], mappings["B"]
    mappings["D"] = args.mapping_d.resolve()
    servers = {c: s for c, s in resolve_servers(repo, mappings, plan).items() if c in wanted}
    if args.database:
        servers = {
            c: CandidateServer(
                s.candidate,
                _with_database(s.app_dsn, args.database),
                _with_database(s.admin_dsn, args.database),
                s.mapping_path,
                s.image_local_id,
            )
            for c, s in servers.items()
        }
    missing = [c for c in wanted if c not in servers]
    if missing:
        parser.error(f"no server configured for candidates {missing}")
    results = run(
        repo=repo,
        dataset_dir=args.dataset,
        out_dir=args.out,
        servers=servers,
        plan=plan,
        as_of=args.as_of,
        k=args.k,
        warmup=args.warmup,
        measured=args.measured,
        seed=args.seed,
        purpose=args.purpose,
        twins_path=args.twins.resolve() if args.twins else None,
    )
    brief = {
        c: {
            "strict_macro_recall": r["strict_macro_recall"],
            "p95_ms": r["latency_ms"]["p95"],
            "leaks": len(r["leak_violations"]),
            "not_reproducible": len(r["not_reproducible_queries"]),
        }
        for c, r in results["candidates"].items()
    }
    print(json.dumps({"run_id": results["run_id"], "candidates": brief}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
