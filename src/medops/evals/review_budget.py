"""Durable total budget for review CLI calls, including failed/invalid/retried attempts.

Reserve before launching. Unknown charges stop further calls until explicit reconciliation;
one unfinished reservation also prevents concurrent callers sharing the same budget.
"""

from __future__ import annotations

import fcntl
import json
import os
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from medops.core.canonical import canonical_hash

FORMAT = "review-total-budget-v1"
UNIT = Decimal("0.000001")


def money(value: Any, *, positive: bool = False) -> Decimal:
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise ValueError("budget/cost must be numeric") from None
    if not number.is_finite() or number < 0 or (positive and number == 0):
        raise ValueError("budget/cost must be finite and nonnegative (budget positive)")
    return number.quantize(UNIT, rounding=ROUND_CEILING)


def now() -> str:
    return datetime.now(UTC).isoformat()


class ReviewBudget:
    def __init__(self, path: Path, *, total_usd: float, scope: Mapping[str, Any]):
        self.path = path
        self.limit = money(total_usd, positive=True)
        max_attempts = scope.get("max_attempts")
        if max_attempts is not None and (
            isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1
        ):
            raise ValueError("max_attempts must be a positive integer")
        self.scope = canonical_hash(dict(scope))
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._locked():
            if path.exists():
                self._read()
            else:
                self._write(
                    {
                        "format": FORMAT,
                        "total_budget_usd": str(self.limit),
                        "scope_sha256": self.scope,
                        "scope": dict(scope),
                        "created_at": now(),
                        "attempts": [],
                    }
                )

    @contextmanager
    def _locked(self) -> Iterator[None]:
        with self.path.with_suffix(self.path.suffix + ".lock").open("a") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle, fcntl.LOCK_UN)

    def _read(self) -> dict[str, Any]:
        doc = json.loads(self.path.read_text(encoding="utf-8"))
        if (
            doc.get("format") != FORMAT
            or doc.get("total_budget_usd") != str(self.limit)
            or doc.get("scope_sha256") != self.scope
            or canonical_hash(doc.get("scope")) != self.scope
        ):
            raise ValueError("review budget identity or authorization changed")
        ids = set()
        for attempt in doc["attempts"]:
            if attempt["attempt_id"] in ids or attempt["status"] not in {"reserved", "accounted", "unknown_charge"}:
                raise ValueError("invalid budget attempt history")
            ids.add(attempt["attempt_id"])
            money(attempt["reserved_usd"], positive=True)
            if attempt["status"] == "accounted":
                money(attempt["cost_usd"])
        return doc

    def _write(self, doc: dict[str, Any]) -> None:
        tmp = self.path.with_name(self.path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as handle:
            json.dump(doc, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, self.path)
        directory = os.open(self.path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    @staticmethod
    def _summary(doc: dict[str, Any]) -> dict[str, Any]:
        known = sum((money(a["cost_usd"]) for a in doc["attempts"] if a["status"] == "accounted"), Decimal(0))
        reserved = sum((money(a["reserved_usd"]) for a in doc["attempts"] if a["status"] != "accounted"), Decimal(0))
        return {
            "attempts": len(doc["attempts"]),
            "known_cost_usd": str(known),
            "unresolved_reserved_usd": str(reserved),
            "remaining_usd": str(max(Decimal(0), money(doc["total_budget_usd"]) - known - reserved)),
            "unresolved_attempts": [a["attempt_id"] for a in doc["attempts"] if a["status"] != "accounted"],
            "total_budget_usd": doc["total_budget_usd"],
        }

    def summary(self) -> dict[str, Any]:
        with self._locked():
            return self._summary(self._read())

    def reserve(self, cap_usd: float, *, identity: Mapping[str, Any]) -> dict[str, Any]:
        cap = money(cap_usd, positive=True)
        with self._locked():
            doc = self._read()
            summary = self._summary(doc)
            max_attempts = doc["scope"].get("max_attempts")
            if max_attempts is not None and len(doc["attempts"]) >= max_attempts:
                raise ValueError("review authorization has reached its maximum number of attempts")
            if doc["scope"].get("stop_on_nonvalidated_attempt") and any(
                attempt["status"] == "accounted"
                and (attempt.get("reconciliation") or {}).get("outcome", attempt.get("outcome")) != "validated_reply"
                for attempt in doc["attempts"]
            ):
                raise ValueError("a nonvalidated attempt blocks further spending under this authorization")
            if any(a.get("cli_cap_exceeded") for a in doc["attempts"]):
                raise ValueError("CLI exceeded a reservation; stop and reconcile its budget semantics")
            if summary["unresolved_attempts"]:
                raise ValueError("unfinished or unknown-charge call blocks further spending; reconcile first")
            remaining = money(summary["remaining_usd"])
            if remaining < cap:
                raise ValueError("remaining review budget is smaller than the next call reservation")
            attempt = {
                "attempt_id": uuid.uuid4().hex,
                "status": "reserved",
                "reserved_usd": str(cap),
                "cost_usd": None,
                "started_at": now(),
                "identity": dict(identity),
            }
            doc["attempts"].append(attempt)
            self._write(doc)
            return dict(attempt)

    def reconcile_validated_reply(self, attempt_id: str, *, evidence: Mapping[str, Any]) -> None:
        """Record that an accounted call contained a locally recoverable, fully validated reply."""
        if not evidence:
            raise ValueError("validated-reply reconciliation requires evidence")
        reconciliation = {
            "outcome": "validated_reply",
            "reconciled_at": now(),
            "evidence": dict(evidence),
        }
        with self._locked():
            doc = self._read()
            attempt = next((a for a in doc["attempts"] if a["attempt_id"] == attempt_id), None)
            if attempt is None or attempt["status"] != "accounted" or attempt.get("outcome") == "validated_reply":
                raise ValueError("only an accounted nonvalidated attempt can be reconciled")
            existing = attempt.get("reconciliation")
            if existing is not None:
                if existing.get("outcome") != "validated_reply" or existing.get("evidence") != dict(evidence):
                    raise ValueError("attempt has a different reconciliation")
                return
            attempt["reconciliation"] = reconciliation
            self._write(doc)

    def finish(self, attempt_id: str, *, cost_usd: Any, outcome: str, metadata: Mapping[str, Any]) -> None:
        cost = None if cost_usd is None else money(cost_usd)
        with self._locked():
            doc = self._read()
            attempt = next((a for a in doc["attempts"] if a["attempt_id"] == attempt_id), None)
            if attempt is None or attempt["status"] != "reserved":
                raise ValueError("attempt cannot be settled twice or without a reservation")
            attempt.update(
                status="unknown_charge" if cost is None else "accounted",
                cost_usd=str(cost) if cost is not None else None,
                finished_at=now(),
                outcome=outcome,
                metadata=dict(metadata),
            )
            if cost is not None and cost > money(attempt["reserved_usd"]):
                attempt["cli_cap_exceeded"] = True
            self._write(doc)
