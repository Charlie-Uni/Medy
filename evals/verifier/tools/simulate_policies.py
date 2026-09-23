"""Offline policy study for the rules/model division of labour (DEC-003), using recorded model verdicts.

    python evals/verifier/tools/simulate_policies.py results_claude-haiku-4-5.json [results_claude-sonnet-5.json ...]

Policies (what the rules are allowed to decide without the model):
  model_only      the model decides every pair
  rules_decisive  current: every element verdict came from a rule (conf >= 0.9) -> keep rules, else model
  polarity+contain rules decide only (a) contradictions from negation polarity / exact-value mismatch and
                  (b) whole-statement containment with the same polarity; everything else -> model
  polarity_only   rules decide only polarity-based contradictions and same-polarity containment; numeric
                  single-value mismatches are left to the model
Each row: shared pairs, model calls needed, accuracy, unsafe accept rate, per-kind accuracy.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "evals/verifier/tools"))
from common import evidence_from_pair, predict_from_result  # noqa: E402
from compare_arms import metrics  # noqa: E402

from medops.domain.answer import Claim  # noqa: E402
from medops.domain.verification import ElementKind, Verdict  # noqa: E402
from medops.verification.verifier import verify_claims  # noqa: E402

POLICIES = ("model_only", "rules_decisive", "polarity+contain", "polarity_only")


def rules_decision(p: dict, single_value: bool) -> tuple[str, dict]:
    ev = evidence_from_pair(p)
    vr = verify_claims(
        [Claim(text=p["statement"], citation_chunk_ids=(p["evidence_chunk_id"],))],
        [ev],
        single_value_contradiction=single_value,
    )
    pred, decisive = predict_from_result(vr)
    polarity_contra = any(
        e.verdict is Verdict.contradicted and e.confidence >= 0.9 and "polarity" in e.reason for e in vr.elements
    )
    value_contra = any(e.verdict is Verdict.contradicted and "evidence states" in e.reason for e in vr.elements)
    contained_ok = any(
        e.kind is ElementKind.statement and e.verdict is Verdict.supported and e.confidence >= 1.0 for e in vr.elements
    )
    return pred, {"decisive": decisive, "polarity_contra": polarity_contra, "value_contra": value_contra, "contained": contained_ok}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("models", nargs="+", type=pathlib.Path)
    ap.add_argument("--pairs", type=pathlib.Path, default=REPO / "evals/verifier/dec003/pairs.jsonl")
    ap.add_argument("--out", type=pathlib.Path, default=REPO / "evals/verifier/dec003/policies.md")
    args = ap.parse_args()
    pairs = {json.loads(l)["pair_id"]: json.loads(l) for l in args.pairs.read_text(encoding="utf-8").splitlines() if l.strip()}
    lines = ["# DEC-003 division-of-labour policies (offline, recorded model verdicts)", ""]
    header = "| model | policy | pairs | model calls | accuracy | unsafe accept | negation | numeric | same_doc | other_doc | supported |"
    lines += [header, "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    cache: dict[str, tuple] = {}
    for path in args.models:
        data = json.loads(path.read_text(encoding="utf-8"))
        mrows = {r["pair_id"]: r for r in data["per_pair"]}
        shared = sorted(set(mrows) & set(pairs))
        for policy in POLICIES:
            rows, calls = [], 0
            for pid in shared:
                p = pairs[pid]
                if pid not in cache:
                    cache[pid] = (rules_decision(p, True), rules_decision(p, False))
                (pred_sv, f_sv), (pred_nosv, f_nosv) = cache[pid]
                if policy == "model_only":
                    use_rules, pred = False, ""
                elif policy == "rules_decisive":
                    use_rules, pred = f_sv["decisive"], pred_sv
                elif policy == "polarity+contain":
                    use_rules = f_sv["polarity_contra"] or f_sv["value_contra"] or f_sv["contained"]
                    pred = pred_sv
                else:
                    use_rules = f_nosv["polarity_contra"] or f_nosv["contained"]
                    pred = pred_nosv
                if not use_rules:
                    calls += 1
                    pred = mrows[pid]["pred"]
                rows.append({"pair_id": pid, "label": p["label"], "pred": pred, "kind": p["kind"], "slices": p["slices"], "dept": p["dept"]})
            m = metrics(rows)
            k = m["by_kind"]
            lines.append(
                f"| {data['model']} | {policy} | {len(shared)} | {calls} ({calls / len(shared):.0%}) | {m['accuracy']:.3f} | {m['unsafe_accept_rate']:.3f} | "
                f"{k.get('contradicted/negation', 0):.3f} | {k.get('contradicted/numeric', 0):.3f} | {k.get('not_supported/same_doc', 0):.3f} | "
                f"{k.get('not_supported/other_doc', 0):.3f} | {k.get('supported', 0):.3f} |"
            )
    lines.append("")
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
