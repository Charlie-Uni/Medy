"""Audit the unchanged v7 renderer on archived evidence, with current AND/OR gold semantics.

This is an exposed-context diagnostic, not fresh retrieval, answer quality, safety or a release gate.
Only the local pinned BGE scorer runs. Full contexts stay in an ignored local snapshot; committed
outputs contain hashes, scores and retention decisions. Query changes are reported separately.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import math
import re
import time
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import Any

from medops.core.canonical import canonical_hash
from medops.domain.evidence import Evidence
from medops.harness.evidence_focus import render_evidence
from medops.harness.focus_profiles import FOCUS_PARAMS

ROOT = Path(__file__).resolve().parents[1]
MODE = "sentfocus-v7"
RISK_PATTERNS = {
    "numeric": re.compile(r"\d"),
    "negation": re.compile(r"\b(?:not|no|never|unless|without|except|contraindicat\w*)\b|不|勿|禁|無|无|除外", re.I),
    "condition": re.compile(
        r"\b(?:if|when|only|unless|except|provided|subject to)\b|若|如果|只有|限於|限于|情況|情况", re.I
    ),
}


def squash(text: str) -> str:
    """Keep elision markers: removing them could falsely join separated evidence into a retained key."""
    return "".join(unicodedata.normalize("NFKC", text).split()).lower()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def save(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def inspect_gold(
    gold: Sequence[Mapping[str, Any]],
    mapping: Mapping[str, Mapping[str, Any]],
    original: Mapping[str, str],
    focused: Mapping[str, str],
) -> dict[str, Any]:
    """OR across a gold's mapped alternatives; AND across required golds. Missing stays in the denominator.

    Key retention and full annotated-span retention are distinct lexical checks, neither proves semantics.
    A mapped chunk without the key is unlocatable, never counted as a retained key.
    """
    rows = []
    for item in gold:
        gid = item["gold_id"]
        entry = mapping.get(gid)
        if entry is None:
            raise ValueError("gold is absent from the bound mapping")
        candidates = list(entry["chunk_ids"]) if entry["status"] == "mapped" else []
        available = [cid for cid in candidates if cid in original]
        key, span = squash(item["key_text"]), squash(item["evidence_span"]["text"])
        if not key or not span:
            raise ValueError("empty annotated key/span")
        located = [cid for cid in available if key in squash(original[cid])]
        kept = [cid for cid in located if key in squash(focused[cid])]
        span_located = [cid for cid in available if span in squash(original[cid])]
        span_kept = [cid for cid in span_located if span in squash(focused[cid])]
        status = (
            "unmappable"
            if entry["status"] != "mapped"
            else "not_in_context"
            if not available
            else "key_unlocatable"
            if not located
            else "retained"
            if kept
            else "hidden_by_focus"
        )
        rows.append(
            {
                "gold_id": gid,
                "status": status,
                "mapped_chunks": candidates,
                "located_chunks": located,
                "kept_chunks": kept,
                "key_sha256": text_hash(item["key_text"]),
                "span_sha256": text_hash(item["evidence_span"]["text"]),
                "span_located_chunks": span_located,
                "span_kept_chunks": span_kept,
                "risk_markers": [
                    name for name, pattern in RISK_PATTERNS.items() if pattern.search(item["evidence_span"]["text"])
                ],
            }
        )
    return {
        "gold": rows,
        "required_groups": len(rows),
        "all_keys_before": bool(rows) and all(r["located_chunks"] for r in rows),
        "all_keys_after": bool(rows) and all(r["kept_chunks"] for r in rows),
        "all_spans_before": bool(rows) and all(r["span_located_chunks"] for r in rows),
        "all_spans_after": bool(rows) and all(r["span_kept_chunks"] for r in rows),
    }


class RecordingScorer:
    def __init__(self, score: Any) -> None:
        self.score_inner = score
        self.calls: list[dict[str, Any]] = []

    def __call__(self, query: str, texts: Sequence[str]) -> list[float]:
        scores = [float(s) for s in self.score_inner(query, texts)]
        if len(scores) != len(texts) or any(not math.isfinite(s) for s in scores):
            raise ValueError("invalid sentence score vector")
        self.calls.append(
            {"query_sha256": text_hash(query), "unit_sha256": [text_hash(t) for t in texts], "scores": scores}
        )
        return scores


def audit_case(case: Mapping[str, Any], score: Any) -> dict[str, Any]:
    items = [Evidence.model_validate(e) for e in case["evidence"]]
    recorder = RecordingScorer(score)
    start = time.perf_counter()
    rendered = render_evidence(
        case["query"], items, mode=MODE, scorer=recorder, rewritten=case["rewritten"], titles=case["titles"]
    )
    elapsed = time.perf_counter() - start
    # Search only the body, never aliases, legend, version, title or rule-line text.
    focused = {
        e.citation.chunk_id: block.split("\n", 1)[1].rsplit("\n", 1)[0]
        for e, block in zip(items, rendered.blocks, strict=True)
    }
    retention = inspect_gold(case["gold"], case["mapping"], {e.citation.chunk_id: e.text for e in items}, focused)
    off = render_evidence(case["query"], items)
    from medops.infrastructure.llm.gateway import estimate_tokens

    return {
        "sample_id": case["sample_id"],
        "dept": case["dept"],
        "language": case["language"],
        "slices": case["slices"],
        "query_changed": case["query_changed"],
        "query_sha256": text_hash(case["query"]),
        "evidence": [{"chunk_id": e.citation.chunk_id, "sha256": e.evidence_text_hash} for e in items],
        "titles_sha256": canonical_hash(case["titles"]),
        "rendered_sha256": text_hash(rendered.body()),
        "legend_sha256": text_hash(rendered.legend),
        "prompt_body_estimate": {"off": estimate_tokens(off.body()), MODE: estimate_tokens(rendered.body())},
        "focus_seconds": elapsed,
        "evidence_tokens_full": rendered.full_tokens,
        "evidence_tokens_kept": rendered.kept_tokens,
        "units": rendered.units,
        "kept_units": rendered.kept_units,
        "scorer_calls": recorder.calls,
        **retention,
    }


def summarize(rows: Sequence[dict[str, Any]]) -> dict[str, Any]:
    def panel(items: Sequence[dict[str, Any]]) -> dict[str, Any]:
        gold = [g for row in items for g in row["gold"]]
        before = [r for r in items if r["all_keys_before"]]
        span_before = [r for r in items if r["all_spans_before"]]
        return {
            "cases": len(items),
            "gold_status": dict(Counter(g["status"] for g in gold)),
            "required_gold_units": len(gold),
            "complete_key_context_before": len(before),
            "complete_key_context_after": sum(r["all_keys_after"] for r in items),
            "key_complete_to_incomplete": [r["sample_id"] for r in before if not r["all_keys_after"]],
            "complete_span_context_before": len(span_before),
            "complete_span_context_after": sum(r["all_spans_after"] for r in items),
            "span_complete_to_incomplete": [r["sample_id"] for r in span_before if not r["all_spans_after"]],
            "multi_gold_cases": sum(r["required_groups"] > 1 for r in items),
            "hidden_gold": [
                {"sample_id": r["sample_id"], **g} for r in items for g in r["gold"] if g["status"] == "hidden_by_focus"
            ],
            "span_losses": [
                {"sample_id": r["sample_id"], **g}
                for r in items
                for g in r["gold"]
                if g["span_located_chunks"] and not g["span_kept_chunks"]
            ],
        }

    return {
        "formal_gate": False,
        "hosted_model_calls": 0,
        "cost_usd": 0,
        "all_archived_context_diagnostics": panel(rows),
        "unchanged_query": panel([r for r in rows if not r["query_changed"]]),
        "changed_query_stale_context": panel([r for r in rows if r["query_changed"]]),
        "note": "Archived retrieval contexts, current annotations. No fresh BM25 retrieval, answer, safety or semantic completeness claim.",
    }


def main() -> None:
    import psycopg

    from medops.core.config import Settings
    from medops.evals.datasets import read_rows, sha256_file
    from medops.evals.run_conditions import FactGuard, environment_snapshot, fact_snapshot_from_dsn, source_snapshot
    from medops.retrieval.doc_focus import load_titles
    from medops.retrieval.glossary_store import load_versioned_glossary
    from medops.retrieval.pinned import PinnedReranker, PinnedThread
    from medops.retrieval.recheck import recheck_candidates
    from medops.retrieval.rerank import BgeRerankerV2M3
    from medops.retrieval.rewrite import rewrite

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--dataset", type=Path, required=True)
    ap.add_argument("--mapping", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True, help="ignored .local/ snapshot; contains full evidence")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--device", choices=("mps", "cpu"), default="mps")
    ap.add_argument("--as-of", type=date.fromisoformat, required=True)
    ap.add_argument("--glossary", default="glossary-20260926-e4daca58a8e4")
    args = ap.parse_args()
    if args.out.exists() or args.snapshot.exists():
        raise ValueError("refusing to overwrite audit output/snapshot")
    if not args.snapshot.resolve().is_relative_to(ROOT / ".local"):
        raise ValueError("full evidence snapshot must stay under .local")
    manifest = json.loads((args.dataset / "manifest.json").read_text())
    mapping_doc = json.loads(args.mapping.read_text())
    if mapping_doc["dataset_hash"] != manifest["dataset_hash"]:
        raise ValueError("mapping belongs to another dataset")
    mapping = {e["gold_id"]: e for e in mapping_doc["entries"]}
    samples = read_rows(args.dataset / "samples.jsonl")
    stored = {r["sample_id"]: r for r in read_rows(args.run / "rows.jsonl")}
    settings = Settings()
    app_dsn = settings.database_url.get_secret_value()
    admin_dsn = (settings.database_admin_url or settings.database_url).get_secret_value()
    before = fact_snapshot_from_dsn(admin_dsn)
    guard = FactGuard({"production": before}, {"production": lambda: fact_snapshot_from_dsn(admin_dsn)})
    glossary = load_versioned_glossary(ROOT / "evals/glossary", args.glossary)
    cases, no_context = [], []
    with psycopg.connect(app_dsn, connect_timeout=5, options="-c statement_timeout=5000") as conn:
        conn.read_only = True
        conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
        for sample in samples:
            sid = sample["sample_id"]
            old = stored.get(sid)
            if old is None or not old.get("evidence_chunks"):
                no_context.append({"sample_id": sid, "required_gold_units": len(sample["required_gold_evidence"])})
                continue
            conn.execute("select set_config('medops.dept', %s, true)", (sample["dept"],))
            checked = recheck_candidates(conn, old["evidence_chunks"], as_of=args.as_of)
            if checked.rejected:
                raise ValueError(f"{sid}: archived evidence failed current fact recheck")
            titles = load_titles(conn, sorted({e.citation.doc_id for e in checked.evidence}))
            cases.append(
                {
                    "sample_id": sid,
                    "dept": sample["dept"],
                    "language": sample["language"],
                    "slices": sample["slices"],
                    "query": sample["query"],
                    "query_changed": sample["query"] != old["query"],
                    "rewritten": rewrite(sample["query"], glossary=glossary).queries,
                    "gold": sample["required_gold_evidence"],
                    "mapping": {g["gold_id"]: mapping[g["gold_id"]] for g in sample["required_gold_evidence"]},
                    "titles": titles,
                    "evidence": [e.model_dump(mode="json") for e in checked.evidence],
                }
            )
    guard.check(force=True)
    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    save(args.snapshot, cases)
    args.out.mkdir(parents=True)
    lane = PinnedThread()
    scorer = PinnedReranker(lane.call(lambda: BgeRerankerV2M3(device=args.device)), lane)
    source = source_snapshot(ROOT, Path(__file__))
    files = [args.run / "rows.jsonl", args.dataset / "samples.jsonl", args.dataset / "manifest.json", args.mapping]
    plan = {
        "format": "focus-candidate-audit-v1",
        "mode": MODE,
        "params": dataclasses.asdict(FOCUS_PARAMS[MODE]),
        "dataset_hash": manifest["dataset_hash"],
        "files": {str(p.resolve().relative_to(ROOT)): sha256_file(p) for p in files},
        "facts": before,
        "source": source,
        "environment": environment_snapshot(),
        "scorer": scorer.spec.model_dump(),
        "device": args.device,
        "as_of": args.as_of.isoformat(),
        "glossary": args.glossary,
        "snapshot_sha256": sha256_file(args.snapshot),
        "snapshot_path": str(args.snapshot.resolve().relative_to(ROOT)),
        "cases": len(cases),
        "no_archived_context": no_context,
        "formal_gate": False,
    }
    save(args.out / "plan.json", plan)
    rows = []
    with (args.out / "rows.jsonl").open("w", encoding="utf-8") as output:
        for n, case in enumerate(cases, 1):
            guard.check()
            row = audit_case(case, scorer.score)
            rows.append(row)
            output.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")
            output.flush()
            if n % 25 == 0:
                print(f"focus audit {n}/{len(cases)}", flush=True)
    guard.check(force=True)
    if source_snapshot(ROOT, Path(__file__)) != source or any(
        sha256_file(ROOT / p) != h for p, h in plan["files"].items()
    ):
        raise ValueError("source/dataset/run inputs changed during audit")
    summary = summarize(rows)
    summary["no_archived_context"] = no_context
    summary["fact_checks"] = guard.checks
    save(args.out / "results.json", summary)
    save(
        args.out / "artifact_manifest.json", {p.name: sha256_file(p) for p in sorted(args.out.iterdir()) if p.is_file()}
    )
    print(
        json.dumps({"cases": len(rows), "unchanged_query": summary["unchanged_query"]}, ensure_ascii=False), flush=True
    )


if __name__ == "__main__":
    main()
