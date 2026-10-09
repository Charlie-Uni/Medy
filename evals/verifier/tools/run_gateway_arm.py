"""DEC-003 API arms through the runtime Model Gateway (ADR-0010): one pair per call, JSON schema, priced.

    python evals/verifier/tools/run_gateway_arm.py --model gpt-6-luna --mode llm|hybrid [--limit 300 --seed 1]

`llm`    : the judge alone decides every pair (measures the model).
`hybrid` : the production path `verify_claims(gateway=...)` — rules first, judge only where rules are undetermined.
Cost is charged to the monthly ledger; the cap from Settings applies. Resumable per pair via <out>.verdicts.jsonl.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import random
import sys
import time

REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "evals/verifier/tools"))
from common import evidence_from_pair, predict_from_result, report_markdown  # noqa: E402
from run_rules_arm import summarize  # noqa: E402

from medops.core.config import Settings  # noqa: E402
from medops.core.errors import InfrastructureError  # noqa: E402
from medops.domain.answer import Claim  # noqa: E402
from medops.infrastructure.llm.factory import build_budgeted_gateway  # noqa: E402
from medops.infrastructure.llm.gateway import (  # noqa: E402
    BudgetExceeded,
    ModelOutputInvalid,
)
from medops.verification.verifier import _llm_judge, verify_claims  # noqa: E402


class _Meter:
    def __init__(self, inner):
        self._inner = inner
        self.calls = 0
        self.cost = 0.0
        self.tokens = 0

    @property
    def provider(self):
        return self._inner.provider

    def complete(self, request):
        r = self._inner.complete(request)
        self.calls += 1
        self.cost += r.cost_usd
        self.tokens += r.usage.total_tokens
        return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--mode", choices=("llm", "hybrid"), default="llm")
    ap.add_argument("--pairs", type=pathlib.Path, default=REPO / "evals/verifier/dec003/pairs.jsonl")
    ap.add_argument("--out", type=pathlib.Path, default=None)
    ap.add_argument("--limit", type=int, default=300)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=30.0)
    args = ap.parse_args()
    out = args.out or REPO / f"evals/verifier/dec003/results_openai-{args.model}-{args.mode}.json"
    verdict_path = out.with_suffix(".verdicts.jsonl")
    settings = Settings()
    gateway = _Meter(build_budgeted_gateway(settings))
    pairs = [json.loads(l) for l in args.pairs.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        pairs = random.Random(args.seed).sample(pairs, min(args.limit, len(pairs)))
    done: dict[str, dict] = {}
    if verdict_path.exists():
        for l in verdict_path.read_text(encoding="utf-8").splitlines():
            if l.strip():
                v = json.loads(l)
                done[v["pair_id"]] = v
    pending = [p for p in pairs if p["pair_id"] not in done]
    print(f"{len(pairs)} pairs, {len(done)} judged, {len(pending)} pending; {args.model} / {args.mode}")
    failures = []
    started = time.perf_counter()
    with verdict_path.open("a", encoding="utf-8") as fh:
        for i, p in enumerate(pending, 1):
            ev = evidence_from_pair(p)
            try:
                if args.mode == "llm":
                    verdict, _chunk, reason = _llm_judge(gateway, args.model, p["statement"], [ev], args.timeout)
                    pred, decisive = verdict.value, False
                else:
                    vr = verify_claims(
                        [Claim(text=p["statement"], citation_chunk_ids=(p["evidence_chunk_id"],))],
                        [ev],
                        gateway=gateway,
                        judge_model_id=args.model,
                        timeout_s=args.timeout,
                    )
                    pred, decisive = predict_from_result(vr)
                    reason = "; ".join(e.reason for e in vr.elements)[:300]
            except BudgetExceeded as exc:
                print(f"stopped: {exc}")
                break
            except (InfrastructureError, ModelOutputInvalid) as exc:
                failures.append({"pair_id": p["pair_id"], "error": f"{type(exc).__name__}: {str(exc)[:200]}"})
                continue
            v = {
                "pair_id": p["pair_id"],
                "verdict": pred,
                "reason": reason,
                "rules_decisive": decisive,
                "model": args.model,
            }
            done[p["pair_id"]] = v
            fh.write(json.dumps(v, ensure_ascii=False) + "\n")
            fh.flush()
            if i % 25 == 0:
                print(
                    f"  {i}/{len(pending)}: {gateway.calls} calls, ${gateway.cost:.3f}, {time.perf_counter() - started:.0f}s"
                )
    rows = [
        {
            "pair_id": p["pair_id"],
            "label": p["label"],
            "pred": done[p["pair_id"]]["verdict"],
            "kind": p["kind"],
            "slices": p["slices"],
            "dept": p["dept"],
            "rules_decisive": done[p["pair_id"]].get("rules_decisive", False),
        }
        for p in pairs
        if p["pair_id"] in done
    ]
    result = summarize(rows, arm=f"openai-{args.mode}", model=args.model, cost_usd=gateway.cost)
    result["calls"] = gateway.calls
    result["tokens"] = gateway.tokens
    result["failures"] = failures
    result["unjudged"] = [p["pair_id"] for p in pairs if p["pair_id"] not in done]
    result["finished_at"] = dt.datetime.now(dt.UTC).isoformat()
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out.with_suffix(".md").write_text(report_markdown(result), encoding="utf-8")
    print(
        json.dumps(
            {k: result[k] for k in ("arm", "model", "n", "accuracy", "unsafe_accept_rate", "cost_usd", "calls")},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
