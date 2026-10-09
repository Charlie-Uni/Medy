"""Build and freeze the Loop replay set (M4-06, DEC-014, records 79/135).

    python evals/replay/tools/build_replay_set.py --out NEW_VERSION --main-run RUN --safety-run RUN \
        --main-set FROZEN_MAIN --safety-set FROZEN_SAFETY [--subset 200] [--seed 20260925]
    python evals/replay/tools/build_replay_set.py --check evals/replay/replay-v1

Historical sources (record 74 C, approved 2026-09-25): the frozen main set `main-v1-provisional` as exercised by the v2 full run
(`evals/harness/runs/2026-09-23-full-ask-v2`, last row per sample) and the safety set drafts as exercised by the second
provisional safety run (`evals/harness/runs/2026-09-24-safety-v1-draft-r2`). Items are *run exports*, not live traffic,
and the manifest says so; the set is replaced when real traces exist. New exports require complete, dataset-bound
runs using the current scoring version and full sample input hashes. Their safety samples are embedded verbatim;
no new export or execution reads mutable drafts. Historical checks/labels remain available without rewriting files.

Legacy labels (unversioned source rows) come from the sample kind and observed outcome.
New versioned rows use medops.evals.main_scoring and carry their expectation/scoring version;
system failures are bad. The table below documents historical exports only:

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

from medops.core.canonical import canonical_hash
from medops.evals.datasets import load_frozen_dataset, read_rows, sha256_file
from medops.evals.main_scoring import SCORING_BINDING, SCORING_VERSION, main_success, validate_row_scoring
from medops.evals.replay_inputs import (
    SAFETY_INPUT_FORMAT,
    safety_samples_for_replay,
    validate_complete_source_rows,
    validate_source_run,
)
from medops.evals.safety_data import write_jsonl

REPO = pathlib.Path(__file__).resolve().parents[3]
MAIN_RUN = REPO / "evals/harness/runs/2026-09-23-full-ask-v2"
SAFETY_RUN = REPO / "evals/harness/runs/2026-09-24-safety-v1-draft-r2"
MAIN_SET = REPO / "evals/main_set/main-v1-provisional"
SAFETY_SET = REPO / "evals/safety_set/safety-v2-provisional"
SPEC_VERSION = "spec-r1 v0.2"
MAIN_DATASET_VERSION = "main-v1-provisional"  # compatibility default for the historical row-export helper


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
    if row.get("scoring_version") is not None:
        validate_row_scoring([row])
        passed = main_success(row, outcome, row.get("cited_chunks", []), row.get("reason_codes", []))
        if not passed and "system_failure" in row.get("reason_codes", []):
            return "bad", "system_failure"
        if kind == "no_answer":
            if passed:
                return "good", "no_answer_expected_insufficient_evidence"
            return "bad", "no_answer_answered" if outcome == "answered" else "no_answer_unexpected_outcome"
        gold = passed

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
    samples: dict[str, dict[str, Any]],
    rows: dict[str, dict[str, Any]],
    versions: dict[str, Any],
    *,
    dataset_version: str = MAIN_DATASET_VERSION,
    source_run: pathlib.Path = MAIN_RUN,
) -> list[dict[str, Any]]:
    items = []
    for i, sid in enumerate(sorted(rows), start=1):
        row = rows[sid]
        sample = samples.get(sid, {})
        label, reason = label_main(row)
        items.append(
            {
                "replay_id": f"rp-{i:04d}",
                "source": {"dataset": dataset_version, "run": str(source_run.relative_to(REPO)), "sample_id": sid},
                "dept": row["dept"],
                "kind": row["kind"],
                "language": row.get("language"),
                "slices": list(row.get("slices") or []),
                "query": row["query"],
                "gold_chunks": list(row.get("gold_chunks") or []),
                **(
                    {"required_gold_groups": row["required_gold_groups"], "evidence_rule": "gold-groups-v1"}
                    if "required_gold_groups" in row
                    else {}
                ),
                **(
                    {"expected_behaviour": row.get("expected_behaviour"), "scoring_version": SCORING_VERSION}
                    if row.get("scoring_version") == SCORING_VERSION
                    else {}
                ),
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
    samples: dict[str, dict[str, Any]],
    versions: dict[str, Any],
    not_exercised: set[str],
    *,
    dataset_version: str,
    source_run: pathlib.Path,
) -> list[dict[str, Any]]:
    items = []
    for i, sid in enumerate(sorted(rows), start=1):
        row = rows[sid]
        sample = samples[sid]
        exercised = sid not in not_exercised  # the runner lists unexercised samples in results.json
        if exercised is False:
            label, reason = "not_exercised", str(row["not_exercised"])
        elif row.get("passed"):
            label, reason = "good", "all_checks_passed"
        else:
            label, reason = "bad", "check_failed:" + ",".join(str(c) for c in (row.get("failed_checks") or []))
        items.append(
            {
                "replay_id": f"rs-{i:04d}",
                "source": {
                    "dataset": dataset_version,
                    "run": str(source_run.relative_to(REPO)),
                    "sample_id": sid,
                },
                "dept": row["dept"],
                "category": row["category"],
                "language": row.get("language"),
                "slices": list(row.get("slices") or []),
                "database": row.get("database"),
                "query": row["query"],
                "expected": sample["expected"],
                "historical": sample.get("historical"),
                "sample": sample,
                "sample_sha256": canonical_hash(sample),
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
        if n == 0:
            continue
        if n > len(by_label[label]):
            raise ValueError(f"not enough {label} source items for the requested subset distribution")
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


def build(
    out: pathlib.Path,
    *,
    subset_size: int,
    seed: int,
    bad_share: float,
    main_run: pathlib.Path = MAIN_RUN,
    safety_run: pathlib.Path = SAFETY_RUN,
    main_set: pathlib.Path = MAIN_SET,
    safety_set: pathlib.Path = SAFETY_SET,
) -> dict[str, Any]:
    """Build a new set only from complete, bound runs on frozen sources. Existing sets are never overwritten."""
    if out.exists():
        raise ValueError("replay output already exists; choose a new version directory")
    if subset_size < 1 or not 0 <= bad_share <= 1:
        raise ValueError("subset must be positive and bad_share must be between zero and one")
    main_run, safety_run, main_set = main_run.resolve(), safety_run.resolve(), main_set.resolve()
    main_manifest = load_frozen_dataset(main_set, expected_id="precise_clause_main")
    safety_manifest = load_frozen_dataset(safety_set, expected_id="safety_set")
    main_rows = latest_rows(main_run / "rows.jsonl")
    main_results = json.loads((main_run / "results.json").read_text(encoding="utf-8"))
    safety_rows = latest_rows(safety_run / "rows.jsonl")
    safety_results = json.loads((safety_run / "results.json").read_text(encoding="utf-8"))
    samples = latest_rows(main_set / "samples.jsonl")
    safety_samples = latest_rows(safety_set / "samples.jsonl")
    validate_source_run(main_run, main_manifest, main_results)
    validate_source_run(safety_run, safety_manifest, safety_results)
    validate_complete_source_rows(samples, main_rows, versions=main_results["versions"])
    validate_complete_source_rows(safety_samples, safety_rows, versions=safety_results["versions"], safety=True)
    if main_results.get("scoring") != SCORING_BINDING:
        raise ValueError("new replay exports require current source scoring; historical files stay unchanged")
    if json.loads((main_run / "scoring_binding.json").read_text()) != SCORING_BINDING:
        raise ValueError("source run scoring binding differs from results")
    validate_row_scoring(list(main_rows.values()))
    main_items = build_main_items(
        samples,
        main_rows,
        main_results["versions"],
        dataset_version=main_manifest["dataset_version"],
        source_run=main_run,
    )
    if len(main_items) < 200 or len({it["query"] for it in main_items}) != len(main_items):
        raise ValueError("replay requires at least 200 main items with unique queries")
    not_exercised = set(safety_results.get("not_exercised") or [])
    if not_exercised != {sid for sid, row in safety_rows.items() if row.get("not_exercised")}:
        raise ValueError("safety results not_exercised differs from its source rows")
    safety_items = build_safety_items(
        safety_rows,
        safety_samples,
        safety_results["versions"],
        not_exercised,
        dataset_version=safety_manifest["dataset_version"],
        source_run=safety_run,
    )
    safety_samples_for_replay(
        {"safety_input_format": SAFETY_INPUT_FORMAT, "sources": {"safety": safety_manifest}}, safety_items
    )
    if len([it for it in main_items if not it["derived"]]) < subset_size:
        raise ValueError("subset exceeds the number of non-derived source items")
    subset = draw_subset(main_items, size=subset_size, bad_share=bad_share, seed=seed)
    if len(subset) != subset_size:
        raise ValueError("requested subset cannot be drawn with this label distribution")
    out.mkdir(parents=True, exist_ok=False)
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
        "provisional_reason": f"source review gaps remain: {main_manifest['dataset_version']} and {safety_manifest['dataset_version']}; see their frozen manifests and current review records",
        "origin": "run_export_not_live_traffic",
        "frozen_at": dt.date.today().isoformat(),
        "purpose": "M4 Loop replay set (baseline 5.8, M4-06): independent good / bad items replayed under a candidate policy; the safety items are the separate safety regression set.",
        "sources": {
            "main": {
                "dataset_version": main_manifest["dataset_version"],
                "dataset_hash": main_manifest["dataset_hash"],
                "run": str(main_run.relative_to(REPO)),
                "rows_sha256": sha256_file(main_run / "rows.jsonl"),
                "results_sha256": sha256_file(main_run / "results.json"),
                "dataset_binding_sha256": sha256_file(main_run / "dataset_binding.json"),
                "dataset_manifest_sha256": sha256_file(main_set / "manifest.json"),
                "versions": main_results["versions"],
            },
            "safety": {
                "dataset_version": safety_manifest["dataset_version"],
                "dataset_hash": safety_manifest["dataset_hash"],
                "run": str(safety_run.relative_to(REPO)),
                "rows_sha256": sha256_file(safety_run / "rows.jsonl"),
                "results_sha256": sha256_file(safety_run / "results.json"),
                "dataset_binding_sha256": sha256_file(safety_run / "dataset_binding.json"),
                "dataset_manifest_sha256": sha256_file(safety_set / "manifest.json"),
                "versions": safety_results["versions"],
            },
        },
        "safety_input_format": SAFETY_INPUT_FORMAT,
        "labels": {
            "main_scoring": main_results.get("scoring", {"version": "legacy-unbound"}),
            "main": "main-outcome-v2 for versioned source rows; otherwise historical build_replay_set.py table",
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
    if manifest.get("safety_input_format"):
        try:
            safety_samples_for_replay(manifest, read_rows(out / "safety_items.jsonl"))
        except (ValueError, KeyError) as exc:
            problems.append(str(exc))
    return problems


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=None)
    ap.add_argument(
        "--main-run",
        type=pathlib.Path,
        default=None,
        help="full main-set run directory (rows.jsonl + results.json)",
    )
    ap.add_argument("--safety-run", type=pathlib.Path, default=None, help="complete, bound safety run directory")
    ap.add_argument("--safety-set", type=pathlib.Path, default=SAFETY_SET, help="frozen safety inputs used by that run")
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
    if args.main_run is None or args.safety_run is None:
        ap.error("new exports require explicit --main-run and --safety-run on frozen inputs")
    manifest = build(
        pathlib.Path(args.out),
        subset_size=args.subset,
        seed=args.seed,
        bad_share=args.bad_share,
        main_run=args.main_run,
        safety_run=args.safety_run,
        main_set=args.main_set,
        safety_set=args.safety_set,
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
