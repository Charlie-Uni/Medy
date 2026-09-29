"""Adapt (M4-03, record 80): from attributed cases to structured candidate diffs — never code, never released.

What Adapt does:

1. `propose`: groups attributed cases by (effective attribution, department) and, per group with enough support, says
   which policy kind a fix would be (`retrieval` -> retrieval_params, `intent` / `safety` -> rule, `generation` ->
   prompt, `knowledge_gap` -> a document ticket, not a policy) and whether a bounded, deterministic diff exists. In
   this build only retrieval parameters can be derived mechanically (raise a channel k that is below the baseline cap
   of 20); prompt and rule content needs an author (a human, or later a model pass), so those groups are reported as
   `needs_author` with the case ids as evidence.
2. `submit`: validates an authored or proposed candidate (allowed kinds `prompt` / `rule` / `skill` /
   `retrieval_params`, a diff of the documented shape, evidence naming the cases) and the isolation rule, then writes
   it as a `candidate` through the Loop role. Release, decision and the gate stay with humans (record 75).

Isolation (INV-EVAL-01): a candidate may cite Loop cases and traces only. Any reference to a replay / evaluation
item (ids `rp-####`, `rs-####`, `ms-####`, `pc-####`, `ss-####`) or any diff string equal to a replay query is refused,
so frozen evaluation material never shapes a candidate.

    python -m medops.loop.adapt propose [--min-support 3]           (DATABASE_LOOP_URL)
    python -m medops.loop.adapt submit --file candidate.json --by <pseudonym>
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any

from medops.application.policy_loader import (
    RETRIEVAL_PARAM_KEYS,
    PolicyDiffError,
    ReleasedPolicySet,
    load_released,
    validate_diff,
)
from medops.domain.state import MAX_CANDIDATES
from medops.loop.reflect import effective_attribution
from medops.retrieval.hybrid import HybridConfig

ALLOWED_KINDS = frozenset({"prompt", "rule", "skill", "retrieval_params"})
KIND_FOR_ATTRIBUTION = {
    "retrieval": "retrieval_params",
    "intent": "rule",
    "safety": "rule",
    "generation": "prompt",
    "knowledge_gap": None,  # tickets (medops.loop.tickets), never a policy
}
EVAL_ID = re.compile(r"\b(?:rp|rs|ms|pc|ss)-\d{4}\b")
REPLAY_ROOT = pathlib.Path(__file__).resolve().parents[3] / "evals" / "replay"
REPLAY_DIR = REPLAY_ROOT / "replay-v1"  # first frozen set; replay_queries() covers every replay-v* directory


class IsolationError(ValueError):
    """The candidate references frozen evaluation material (INV-EVAL-01)."""


# ------------------------------------------------------------------------------------------ proposals


@dataclass(frozen=True)
class Proposal:
    attribution: str
    dept: str
    case_ids: tuple[str, ...]
    suggested_kind: str | None
    auto_diff: dict[str, Any] | None
    needs_author: bool
    note: str


def propose(cases: Iterable[Mapping[str, Any]], *, current: HybridConfig, min_support: int = 3) -> list[Proposal]:
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for c in cases:
        attribution = effective_attribution(dict(c))
        if attribution:
            groups[(attribution, str(c["dept"]))].append(str(c["case_id"]))
    out: list[Proposal] = []
    for (attribution, dept), ids in sorted(groups.items()):
        if len(ids) < min_support:
            continue
        kind = KIND_FOR_ATTRIBUTION.get(attribution)
        auto = retrieval_auto_diff(current) if attribution == "retrieval" else None
        if kind is None:
            note = "knowledge gaps become document tickets, not policies"
        elif auto:
            note = "channel k below the baseline cap: raising it is the one mechanical retrieval change"
        elif attribution == "retrieval":
            note = f"channel k already at the cap {MAX_CANDIDATES}; rrf_k / reranker changes need an authored candidate"
        else:
            note = f"{kind} content needs an author (human or a later model pass); cite these cases as evidence"
        out.append(
            Proposal(
                attribution=attribution,
                dept=dept,
                case_ids=tuple(sorted(ids)),
                suggested_kind=kind,
                auto_diff=auto,
                needs_author=kind is not None and auto is None,
                note=note,
            )
        )
    return out


def retrieval_auto_diff(current: HybridConfig) -> dict[str, Any] | None:
    diff: dict[str, Any] = {}
    if current.k_lexical < MAX_CANDIDATES:
        diff["k_lexical"] = {"from": current.k_lexical, "to": MAX_CANDIDATES}
    if current.k_vector < MAX_CANDIDATES:
        diff["k_vector"] = {"from": current.k_vector, "to": MAX_CANDIDATES}
    return diff or None


# ------------------------------------------------------------------------------------------ candidates


@dataclass(frozen=True)
class Candidate:
    kind: str
    name: str
    diff: dict[str, Any]
    evidence: dict[str, Any]
    created_by: str
    version: str = field(default="")

    def with_version(self, today: dt.date | None = None) -> Candidate:
        digest = hashlib.sha256(json.dumps(self.diff, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:8]
        return Candidate(
            self.kind,
            self.name,
            self.diff,
            self.evidence,
            self.created_by,
            f"{self.name}@{(today or dt.date.today()).isoformat()}-{digest}",
        )


def _strings(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for k, v in value.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from _strings(v)


def replay_queries(replay_dir: pathlib.Path | None = None) -> frozenset[str]:
    """Queries of every frozen replay set (INV-EVAL-01): one directory when given, else all `replay-v*` under
    evals/replay, so a candidate can never quote an item of an older or a newer set."""
    dirs = [replay_dir] if replay_dir is not None else sorted(REPLAY_ROOT.glob("replay-v*"))
    out: set[str] = set()
    for d in dirs:
        for name in ("items.jsonl", "safety_items.jsonl"):
            path = d / name
            if path.exists():
                for line in path.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        out.add(" ".join(json.loads(line)["query"].split()))
    return frozenset(out)


def check_isolation(candidate: Candidate, *, forbidden_queries: frozenset[str]) -> None:
    for s in _strings({"diff": candidate.diff, "evidence": candidate.evidence, "name": candidate.name}):
        if EVAL_ID.search(s):
            raise IsolationError(f"candidate references an evaluation item id: {EVAL_ID.search(s).group(0)}")  # type: ignore[union-attr]
        if " ".join(s.split()) in forbidden_queries:
            raise IsolationError("candidate contains a replay-set query")


def validate_candidate(candidate: Candidate, *, current: HybridConfig, forbidden_queries: frozenset[str]) -> None:
    if candidate.kind not in ALLOWED_KINDS:
        raise PolicyDiffError(f"kind must be one of {sorted(ALLOWED_KINDS)}")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,63}", candidate.name):
        raise PolicyDiffError("name must be a short lower-case identifier")
    if not isinstance(candidate.diff, Mapping) or not candidate.diff:
        raise PolicyDiffError("diff must be a non-empty JSON object")
    validate_diff(candidate.kind, candidate.name, candidate.diff, base=current)
    if candidate.kind == "retrieval_params":
        for key, entry in candidate.diff.items():
            if key in RETRIEVAL_PARAM_KEYS and isinstance(entry, Mapping) and "from" in entry:
                actual = getattr(current, key, None)
                if actual is not None and entry["from"] != actual:
                    raise PolicyDiffError(f"{key}: `from` {entry['from']} is not the current value {actual}")
    case_ids = candidate.evidence.get("case_ids")
    if (
        not isinstance(case_ids, list)
        or not case_ids
        or not all(re.fullmatch(r"[0-9a-f-]{32,36}", str(c)) for c in case_ids)
    ):
        raise PolicyDiffError("evidence.case_ids must list the Loop cases (uuids) the candidate answers")
    check_isolation(candidate, forbidden_queries=forbidden_queries)


def submit(conn: Any, candidate: Candidate, *, current: HybridConfig, forbidden_queries: frozenset[str]) -> str:
    """Validate, then insert as a candidate through the store (the Loop role may only insert candidates)."""
    from medops.infrastructure.db.policies import PgPolicyStore

    validate_candidate(candidate, current=current, forbidden_queries=forbidden_queries)
    versioned = candidate.with_version() if not candidate.version else candidate
    evidence = {
        **candidate.evidence,
        "adapt": {"version": "adapt-v1", "isolation_check": "passed", "at": dt.datetime.now(dt.UTC).isoformat()},
    }
    return PgPolicyStore(conn).insert_candidate(
        kind=versioned.kind,
        name=versioned.name,
        version=versioned.version,
        diff=dict(versioned.diff),
        evidence=evidence,
        created_by=versioned.created_by,
    )


# ------------------------------------------------------------------------------------------ PostgreSQL + CLI

_CASES_SQL = """
select case_id::text, dept::text, attribution, human_override
  from bad_cases where label = 'bad' and status in ('attributed', 'corrected') order by opened_at
"""


def current_config(conn: Any) -> HybridConfig:
    from medops.retrieval.production import production_hybrid_config

    released: ReleasedPolicySet = load_released(conn)
    return released.hybrid_config(production_hybrid_config())


def main(argv: list[str] | None = None) -> int:
    import psycopg

    from medops.core.config import Settings

    ap = argparse.ArgumentParser(description="Adapt: propose candidate diffs from attributed cases, or submit one")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("propose")
    p.add_argument("--min-support", type=int, default=3)
    s = sub.add_parser("submit")
    s.add_argument("--file", required=True, help="JSON: {kind, name, diff, evidence: {case_ids: [...]}}")
    s.add_argument("--by", required=True, help="author pseudonym or 'loop:<component>'")
    args = ap.parse_args(argv)
    settings = Settings()  # type: ignore[call-arg]
    if settings.database_loop_url is None:
        print("DATABASE_LOOP_URL is not configured", file=sys.stderr)
        return 2
    with (
        psycopg.connect(
            settings.database_loop_url.get_secret_value(),
            connect_timeout=settings.db_connect_timeout_s,
            options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
        ) as conn,
        conn.transaction(),
    ):
        current = current_config(conn)
        if args.cmd == "propose":
            rows = [
                {"case_id": r[0], "dept": r[1], "attribution": r[2], "human_override": r[3]}
                for r in conn.execute(_CASES_SQL).fetchall()
            ]
            print(
                json.dumps(
                    [asdict(x) for x in propose(rows, current=current, min_support=args.min_support)],
                    ensure_ascii=False,
                    indent=1,
                )
            )
            return 0
        spec = json.loads(pathlib.Path(args.file).read_text(encoding="utf-8"))
        candidate = Candidate(
            kind=spec["kind"],
            name=spec["name"],
            diff=spec["diff"],
            evidence=spec.get("evidence") or {},
            created_by=args.by,
        )
        try:
            policy_id = submit(conn, candidate, current=current, forbidden_queries=replay_queries())
        except (PolicyDiffError, IsolationError) as exc:
            print(json.dumps({"refused": type(exc).__name__, "detail": str(exc)}), file=sys.stderr)
            return 1
    print(json.dumps({"policy_id": policy_id}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
