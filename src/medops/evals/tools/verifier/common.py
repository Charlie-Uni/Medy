"""Shared helpers for the DEC-003 arms."""

from __future__ import annotations

import hashlib
from datetime import date

from medops.domain.common import DocStatus
from medops.domain.evidence import Citation, Evidence
from medops.domain.verification import Verdict, VerifyResult


def evidence_from_pair(p: dict) -> Evidence:
    text = p["evidence_text"]
    return Evidence(
        citation=Citation(
            doc_id=p["document_source_hash"][:16],
            version="v",
            effective_date=date(2026, 1, 1),
            page=1,
            section="",
            chunk_id=p["evidence_chunk_id"],
        ),
        text=text,
        evidence_text_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        chunk_content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        status=DocStatus.active,
    )


def predict_from_result(vr: VerifyResult) -> tuple[str, bool]:
    """Collapse element verdicts to one label; `decisive` = every verdict came from a rule (confidence >= 0.9)."""
    if vr.contradicted:
        pred = Verdict.contradicted.value
    elif vr.unsupported:
        pred = Verdict.not_supported.value
    else:
        pred = Verdict.supported.value
    decisive = bool(vr.elements) and all(e.confidence >= 0.9 for e in vr.elements)
    return pred, decisive


def report_markdown(result: dict) -> str:
    lines = [
        f"# DEC-003 arm `{result['arm']}` ({result['model']})",
        "",
        f"- pairs: {result['n']} · accuracy: {result['accuracy']} · unsafe accept rate (non-supported judged supported): {result['unsafe_accept_rate']} · cost: ${result['cost_usd']}",
    ]
    if result.get("rules_decisive_share") is not None:
        lines.append(f"- share of pairs decided by rules alone: {result['rules_decisive_share']}")
    lines += ["", "| kind | n | accuracy |", "| --- | ---: | ---: |"]
    lines += [f"| {k} | {v['n']} | {v['accuracy']} |" for k, v in result["by_kind"].items()]
    lines += ["", "| slice | n | accuracy |", "| --- | ---: | ---: |"]
    lines += [f"| {k} | {v['n']} | {v['accuracy']} |" for k, v in result["by_slice"].items()]
    lines += ["", "| label \\ pred | supported | not_supported | contradicted |", "| --- | ---: | ---: | ---: |"]
    for a, row in result["confusion"].items():
        lines.append(f"| {a} | {row['supported']} | {row['not_supported']} | {row['contradicted']} |")
    lines.append("")
    return "\n".join(lines)
