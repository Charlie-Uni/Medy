"""Build and freeze the Loop replay set (M4-06, DEC-014, record 79).

    python evals/replay/tools/build_replay_set.py --out evals/replay/replay-v1 [--subset 200] [--seed 20260925]
    python evals/replay/tools/build_replay_set.py --check evals/replay/replay-v1

Sources (record 74 C, approved 2026-09-25): the frozen main set `main-v1-provisional` as exercised by the v2 full run
(`evals/harness/runs/2026-09-23-full-ask-v2`, last row per sample) and the safety set drafts as exercised by the second
provisional safety run (`evals/harness/runs/2026-09-24-safety-v1-draft-r2`). Items are *run exports*, not live traffic,
and the manifest says so; the set is replaced when real traces exist.

Labels (main items) come from the sample kind and the observed outcome:

| kind       | observed                          | label | reason                          |
| ---------- | --------------------------------- | ----- | ------------------------------- |
| answerable | answered, gold cited              | good  | answerable_answered_gold_cited  |
| answerable | answered, gold not cited          | bad   | answerable_answered_wrong_citation |
| answerable | escalated                         | bad   | answerable_false_abstention     |
| no_answer  | escalated                         | good  | no_answer_abstained             |
| no_answer  | answered                          | bad   | no_answer_answered              |
| conflict   | answered, current version cited   | good  | conflict_current_cited          |
| conflict   | answered, current not cited       | bad   | conflict_wrong_version          |
| conflict   | escalated                         | bad   | conflict_false_abstention       |

Safety items carry the sample's expectation block and the run's check results; label `good` = every check passed,
`bad` = a check failed, `not_exercised` = the runner's `results.json` lists the sample as not exercised (the injected
chunk was never retrieved; kept, not counted).

The candidate-screening subset (DEC-014: 200 items, three runs ≈ 5 USD) is drawn deterministically: derived samples
(paraphrase twins) are excluded so items are independent, bad cases are oversampled to 30% so a candidate's effect on
failures is measurable, and within each label the departments are represented proportionally.

Isolation (INV-EVAL-01): replay item ids, queries and gold ids never enter Adapt's candidate-generation context; the
manifest states the rule and M4-03 enforces it when candidates are produced.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import random
import sys
from collections import Counter, defaultdict
from typing import Any

REPO = pathlib.Path(__file__).resolve().parents[3]
MAIN_RUN = REPO / "evals/harness/runs/2026-09-23-full-ask-v2"
SAFETY_RUN = REPO / "evals/harness/runs/2026-09-24-safety-v1-draft-r2"
MAIN_SET = REPO / "evals/main_set/main-v1-provisional"
SAFETY_DRAFTS = REPO / "evals/safety_set/drafts"
SPEC_VERSION = "spec-r1 v0.1"
MAIN_DATASET_VERSION = "main-v1-provisional"  # stamped into item sources; build() sets it from the main-set manifest


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latest_rows(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    """rows.jsonl is append-only across resumes; the last row per sample wins (same rule as summarize_run.py)."""
    out: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            out[row["sample_id"]] = row
    return out


def label_main(row: dict[str, Any]) -> tuple[str, str]:
    kind, outcome, gold = row["kind"], row["outcome"], bool(row.get("gold_cited"))
    if kind == "answerable":
        if outcome == "answered":
            return ("good", "answerable_answered_gold_cited") if gold else ("bad", "answerable_answered_wrong_citation")
        return "bad", "answerable_false_abstention"
    if kind == "no_answer":
        return ("good", "no_answer_abstained") if outcome != "answered" else ("bad", "no_answer_answered")
    if kind == "conflict":
        if outcome == "answered":
            return ("good", "conflict_current_cited") if gold else ("bad", "conflict_wrong_version")
        return "bad", "conflict_false_abstention"
    raise ValueError(f"unknown sample kind {kind!r}")


def build_main_items(
    samples: dict[str, dict[str, Any]], rows: dict[str, dict[str, Any]], versions: dict[str, Any]
) -> list[dict[str, Any]]:
    items = []
    for i, sid in enumerate(sorted(rows), start=1):
        row = rows[sid]
        sample = samples.get(sid, {})
        label, reason = label_main(row)
        items.append(
            {
                "replay_id": f"rp-{i:04d}",
                "source": {"dataset": MAIN_DATASET_VERSION, "run": str(MAIN_RUN.relative_to(REPO)), "sample_id": sid},
                "dept": row["dept"],
                "kind": row["kind"],
                "language": row.get("language"),
                "slices": list(row.get("slices") or []),
                "query": row["query"],
                "gold_chunks": list(row.get("gold_chunks") or []),
                "historical": None,
                "imported": bool(row.get("imported")),
                "derived": bool(row.get("derived")) or bool(sample.get("derived_from")),
                "observed": {
                    "outcome": row["outcome"],
                    "reason_codes": list(row.get("reason_codes") or []),
                    "cited_chunks": list(row.get("cited_chunks") or []),
                    "gold_cited": bool(row.get("gold_cited")),
                    "claims": len(row.get("claims") or []),
                    "versions": versions,
                },
                "label": label,
                "label_reason": reason,
            }
        )
    return items


def build_safety_items(
    rows: dict[str, dict[str, Any]],
    drafts: dict[str, dict[str, Any]],
    versions: dict[str, Any],
    not_exercised: set[str],
) -> list[dict[str, Any]]:
    items = []
    for i, sid in enumerate(sorted(rows), start=1):
        row = rows[sid]
        draft = drafts.get(sid, {})
        exercised = sid not in not_exercised  # the runner lists unexercised samples in results.json
        if exercised is False:
            label, reason = "not_exercised", "injected_chunk_not_retrieved"
        elif row.get("passed"):
            label, reason = "good", "all_checks_passed"
        else:
            label, reason = "bad", "check_failed:" + ",".join(str(c) for c in (row.get("failed_checks") or []))
        items.append(
            {
                "replay_id": f"rs-{i:04d}",
                "source": {
                    "dataset": "safety-v1-provisional",
                    "run": str(SAFETY_RUN.relative_to(REPO)),
                    "sample_id": sid,
                },
                "dept": row["dept"],
                "category": row["category"],
                "language": row.get("language"),
                "slices": list(row.get("slices") or []),
                "database": row.get("database"),
                "query": row["query"],
                "expected": row.get("expected") or draft.get("expected"),
                "historical": draft.get("historical"),
                "observed": {
                    "outcome": row.get("outcome"),
                    "api_outcome": row.get("api_outcome"),
                    "reason_codes": list(row.get("reason_codes") or []),
                    "passed": bool(row.get("passed")),
                    "failed_checks": list(row.get("failed_checks") or []),
                    "exercised": exercised,
                    "versions": versions,
                },
                "label": label,
                "label_reason": reason,
            }
        )
    return items


def draw_subset(items: list[dict[str, Any]], *, size: int, bad_share: float, seed: int) -> list[str]:
    """Deterministic stratified draw: no derived items; `bad_share` of the subset from bad items (or all bad items if
    fewer); departments proportional within each label; the remainder filled from the largest strata."""
    rng = random.Random(seed)
    pool = [it for it in items if not it["derived"]]
    by_label: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for it in pool:
        by_label[it["label"]].append(it)
    want_bad = min(int(round(size * bad_share)), len(by_label["bad"]))
    want = {"bad": want_bad, "good": size - want_bad}
    chosen: list[str] = []
    for label, n in want.items():
        strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for it in by_label[label]:
            strata[it["dept"]].append(it)
        total = sum(len(v) for v in strata.values())
        quota = {d: int(n * len(v) / total) for d, v in strata.items()}
        picked: list[dict[str, Any]] = []
        for d in sorted(strata):
            bucket = sorted(strata[d], key=lambda it: it["replay_id"])
            rng.shuffle(bucket)
            picked.extend(bucket[: quota[d]])
            strata[d] = bucket[quota[d] :]
        while len(picked) < n:
            d = max(strata, key=lambda k: len(strata[k]))
            if not strata[d]:
                break
            picked.append(strata[d].pop(0))
        chosen.extend(it["replay_id"] for it in picked)
    return sorted(chosen)


def counts(items: list[dict[str, Any]], *keys: str) -> dict[str, Any]:
    out: dict[str, Any] = {"items": len(items)}
    for k in keys:
        out["by_" + k] = dict(sorted(Counter(str(it.get(k)) for it in items).items()))
    out["by_dept_label"] = dict(sorted(Counter(f"{it['dept']}/{it['label']}" for it in items).items()))
    return out


def write_jsonl(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def build(
    out: pathlib.Path,
    *,
    subset_size: int,
    seed: int,
    bad_share: float,
    main_run: pathlib.Path = MAIN_RUN,
    safety_run: pathlib.Path = SAFETY_RUN,
    main_set: pathlib.Path = MAIN_SET,
) -> dict[str, Any]:
    """A later replay version (replay-v2, ...) is built from a later frozen main set and its full run; the safety
    drafts and their run may stay the same. The sources are recorded in the manifest, never assumed."""
    global MAIN_RUN, SAFETY_RUN, MAIN_DATASET_VERSION  # noqa: PLW0603 - the item builders stamp these into sources
    main_run, safety_run, main_set = main_run.resolve(), safety_run.resolve(), main_set.resolve()
    out.mkdir(parents=True, exist_ok=True)
    main_rows = latest_rows(main_run / "rows.jsonl")
    main_results = json.loads((main_run / "results.json").read_text(encoding="utf-8"))
    safety_rows = latest_rows(safety_run / "rows.jsonl")
    safety_results = json.loads((safety_run / "results.json").read_text(encoding="utf-8"))
    samples = latest_rows(main_set / "samples.jsonl")
    main_manifest = json.loads((main_set / "manifest.json").read_text(encoding="utf-8"))
    run_dataset = (main_results.get("dataset") or {}).get("version")
    if run_dataset not in (None, main_manifest["dataset_version"]):
        raise SystemExit(f"{main_run.name} was run on {run_dataset}, not {main_manifest['dataset_version']}")
    MAIN_RUN, SAFETY_RUN, MAIN_DATASET_VERSION = main_run, safety_run, main_manifest["dataset_version"]
    drafts: dict[str, dict[str, Any]] = {}
    for path in sorted(SAFETY_DRAFTS.glob("samples_draft_*.jsonl")):
        drafts.update(latest_rows(path))

    main_items = build_main_items(samples, main_rows, main_results["versions"])
    safety_items = build_safety_items(
        safety_rows, drafts, safety_results["versions"], set(safety_results.get("not_exercised") or [])
    )
    subset = draw_subset(main_items, size=subset_size, bad_share=bad_share, seed=seed)
    write_jsonl(out / "items.jsonl", main_items)
    write_jsonl(out / "safety_items.jsonl", safety_items)
    by_id = {it["replay_id"]: it for it in main_items}
    (out / "subset.json").write_text(
        json.dumps(
            {
                "name": "candidate-screening",
                "size": len(subset),
                "seed": seed,
                "rule": f"no derived items; bad share {bad_share:.0%} (or all bad items); departments proportional within label",
                "counts": counts([by_id[i] for i in subset], "label", "dept", "kind"),
                "replay_ids": subset,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    files = {name: sha256_file(out / name) for name in ("items.jsonl", "safety_items.jsonl", "subset.json")}
    dataset_hash = hashlib.sha256("".join(f"{h}  {n}\n" for n, h in sorted(files.items())).encode()).hexdigest()
    manifest = {
        "dataset_id": "loop_replay",
        "dataset_version": out.name,
        "spec_version": SPEC_VERSION,
        "status": "frozen",
        "provisional": True,
        "provisional_reason": f"both sources are provisional: {main_manifest['dataset_version']} awaits its second human review, the safety set awaits annotator-01",
        "origin": "run_export_not_live_traffic",
        "frozen_at": dt.date.today().isoformat(),
        "purpose": "M4 Loop replay set (baseline 5.8, M4-06): independent good / bad items replayed under a candidate policy; the safety items are the separate safety regression set.",
        "sources": {
            "main": {
                "dataset_version": main_manifest["dataset_version"],
                "dataset_hash": main_manifest["dataset_hash"],
                "run": str(main_run.relative_to(REPO)),
                "rows_sha256": sha256_file(main_run / "rows.jsonl"),
                "versions": main_results["versions"],
            },
            "safety": {
                "dataset_version": "safety-v1-provisional",
                "run": str(safety_run.relative_to(REPO)),
                "rows_sha256": sha256_file(safety_run / "rows.jsonl"),
                "versions": safety_results["versions"],
            },
        },
        "labels": {
            "main": "see build_replay_set.py docstring table",
            "safety": "good = all checks passed; bad = a check failed; not_exercised = injected chunk not retrieved (kept, not counted)",
        },
        "counts": {
            "main": counts(main_items, "label", "dept", "kind", "language"),
            "safety": counts(safety_items, "label", "category", "dept"),
        },
        "independence": {
            "distinct_queries_main": len({it["query"] for it in main_items}),
            "derived_items_main": sum(it["derived"] for it in main_items),
            "imported_items_main": sum(it["imported"] for it in main_items),
            "statement": "one item per sample; derived (paraphrase twin) items are flagged and excluded from the screening subset; three repeated runs of the same items are never counted as more items (M4-06)",
        },
        "subset": {"file": "subset.json", "size": len(subset), "seed": seed},
        "isolation": "INV-EVAL-01: replay ids, queries and gold ids never enter the Loop's candidate-generation context (Adapt); M4-03 enforces this when candidates are produced.",
        "files": files,
        "dataset_hash": dataset_hash,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "SHA256SUMS").write_text("".join(f"{h}  {n}\n" for n, h in sorted(files.items())), encoding="utf-8")
    return manifest


def check(out: pathlib.Path) -> list[str]:
    problems: list[str] = []
    manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        actual = sha256_file(out / name)
        if actual != expected:
            problems.append(f"{name}: sha256 {actual} != manifest {expected}")
    recomputed = hashlib.sha256(
        "".join(f"{h}  {n}\n" for n, h in sorted(manifest["files"].items())).encode()
    ).hexdigest()
    if recomputed != manifest["dataset_hash"]:
        problems.append("dataset_hash does not match the file hashes")
    items = [
        json.loads(line) for line in (out / "items.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    ids = [it["replay_id"] for it in items]
    if len(ids) != len(set(ids)):
        problems.append("duplicate replay ids")
    if len({it["query"] for it in items}) != len(items):
        problems.append("duplicate queries among main items")
    good_bad = [it for it in items if it["label"] in ("good", "bad")]
    if len(good_bad) < 200:
        problems.append(f"only {len(good_bad)} good/bad items (< 200)")
    subset = json.loads((out / "subset.json").read_text(encoding="utf-8"))
    by_id = {it["replay_id"]: it for it in items}
    missing = [i for i in subset["replay_ids"] if i not in by_id]
    if missing:
        problems.append(f"subset ids not in items: {missing[:5]}")
    if any(by_id[i]["derived"] for i in subset["replay_ids"] if i in by_id):
        problems.append("subset contains derived items")
    if len(subset["replay_ids"]) != subset["size"]:
        problems.append("subset size mismatch")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--main-run",
        type=pathlib.Path,
        default=MAIN_RUN,
        help="full main-set run directory (rows.jsonl + results.json)",
    )
    ap.add_argument("--safety-run", type=pathlib.Path, default=SAFETY_RUN, help="safety run directory")
    ap.add_argument(
        "--main-set", type=pathlib.Path, default=MAIN_SET, help="frozen main-set directory the run exercised"
    )
    ap.add_argument("--check", default=None)
    ap.add_argument("--subset", type=int, default=200)
    ap.add_argument("--seed", type=int, default=20260925)
    ap.add_argument("--bad-share", type=float, default=0.30)
    args = ap.parse_args()
    if args.check:
        problems = check(pathlib.Path(args.check))
        print("\n".join(problems) if problems else "replay set consistent")
        return 1 if problems else 0
    if not args.out:
        ap.error("--out or --check is required")
    manifest = build(
        pathlib.Path(args.out),
        subset_size=args.subset,
        seed=args.seed,
        bad_share=args.bad_share,
        main_run=args.main_run,
        safety_run=args.safety_run,
        main_set=args.main_set,
    )
    print(
        json.dumps(
            {"dataset_hash": manifest["dataset_hash"], "counts": manifest["counts"], "subset": manifest["subset"]},
            ensure_ascii=False,
            indent=1,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
