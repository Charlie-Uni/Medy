"""Constant-space repetition guard over validated, committed tool observations.

This is an execution bound, not a quality/semantic-progress judge. Hashes are
restricted checkpoint metadata, never new evidence or a permission to finish.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from uuid import UUID

from medops.application.agent_tool_results import (
    AgentToolOutcome,
    EvidenceView,
    ExtractionPayload,
    ReadPayload,
    SearchPayload,
    VerificationPayload,
)
from medops.core.canonical import canonical_hash, canonical_json, sha256_hex
from medops.domain.agent_actions import (
    ExtractAEAction,
    ReadEvidenceAction,
    SearchDocumentsAction,
    VerifyCitationsAction,
)
from medops.domain.agent_execution import BoundAction, EvidenceHandle

PROGRESS_VERSION = "pv-progress-v1"
_COSMETIC_PUNCTUATION = str.maketrans({c: " " for c in "!?;。！？；、…"})
_FULLWIDTH_ASCII = str.maketrans({chr(c): chr(c - 0xFEE0) for c in range(0xFF01, 0xFF5F)})


def _query(value: str) -> str:
    # Presentation changes cannot buy another repeated call. Keep case, decimals,
    # signs, comparisons, units, identifiers and negation; do not infer synonyms.
    value = unicodedata.normalize("NFC", value).translate(_FULLWIDTH_ASCII)
    # A numeric comma may be a decimal separator. Never collapse 1,5 into 1 5.
    value = re.sub(r"(?<!\d),|,(?!\d)", " ", value)
    value = value.translate(_COSMETIC_PUNCTUATION).rstrip(" .")
    return re.sub(r"\s+", " ", value).strip()


def _sorted(values: Iterable[object]) -> list[object]:
    unique = {canonical_json(value): value for value in values}
    return [unique[key] for key in sorted(unique)]


def _evidence_key(item: EvidenceHandle) -> str:
    evidence = item.evidence
    return canonical_hash(
        {
            "citation": evidence.citation.model_dump(mode="json"),
            "source_sha256": item.source_sha256,
            "text_sha256": evidence.evidence_text_hash,
            "chunk_content_sha256": evidence.chunk_content_hash,
            "status": evidence.status,
            "historical": evidence.historical,
        }
    )


@dataclass(frozen=True)
class ProgressCheckpoint:
    version: str = PROGRESS_VERSION
    action_sha256: str | None = None
    result_sha256: str | None = None
    consecutive: int = 0


class AgentProgress:
    """Only invoke after result validation and receipt/commit checks.

    A repeated action with an identical stable result contains no new lawful
    evidence/support. New content, longer reads, changed checks and genuinely
    different parameters reset the streak. No persistent recovery is implied.
    """

    def __init__(self) -> None:
        self._state = ProgressCheckpoint()

    def snapshot(self) -> ProgressCheckpoint:
        return self._state

    def reset(self) -> None:
        # An invalid proposal interrupts consecutive committed-tool observations.
        self._state = ProgressCheckpoint()

    def observe(
        self, action: BoundAction, outcome: AgentToolOutcome, registry: tuple[EvidenceHandle, ...]
    ) -> ProgressCheckpoint:
        keys = {h.handle: _evidence_key(h) for h in registry}

        def key(handle: UUID) -> str:
            try:
                return keys[handle]
            except KeyError:
                raise ValueError("agent_progress_unknown_handle") from None

        def view(item: EvidenceView) -> dict[str, object]:
            return {
                "evidence": key(item.handle),
                "char_start": item.char_start,
                "char_end": item.char_end,
                "text_sha256": sha256_hex(item.text),
                "truncated": item.truncated,
            }

        proposal = action.proposal
        params: dict[str, object] = {"action": proposal.action}
        if isinstance(proposal, SearchDocumentsAction):
            params["query"] = _query(proposal.query)
        elif isinstance(proposal, ExtractAEAction):
            params.update(narrative_ref=proposal.narrative_ref, source_type=proposal.source_type)
        elif isinstance(proposal, ReadEvidenceAction):
            params.update(evidence=key(proposal.handle), region=proposal.region)
        elif isinstance(proposal, VerifyCitationsAction):
            params["claims"] = _sorted(
                {
                    "requirement_id": c.requirement_id,
                    "text": c.text,
                    "evidence": sorted({key(h) for h in c.evidence_handles}),
                }
                for c in proposal.claims
            )
        else:
            raise ValueError("agent_progress_requires_tool_action")

        result: dict[str, object] = {"kind": outcome.kind}
        payload = outcome.payload
        # Failed/unsupported payloads are not lawful new information. Only their
        # fixed observation kind enters the stable result (as in PlanningBoard).
        if outcome.kind == "ok":
            if isinstance(payload, SearchPayload):
                result["matches"] = _sorted(view(v) for v in payload.matches)
            elif isinstance(payload, ReadPayload):
                result["evidence"] = view(payload.evidence)
            elif isinstance(payload, ExtractionPayload):
                result.update(
                    skill_status=payload.skill_status,
                    elements=_sorted(e.model_dump(mode="json") for e in payload.elements),
                    missing_kinds=sorted(payload.missing_kinds),
                )
            elif isinstance(payload, VerificationPayload):
                result["checks"] = _sorted(
                    {
                        "requirement_id": c.requirement_id,
                        "text": c.text,
                        "verdict": c.verdict,
                        "requested": sorted({key(h) for h in c.requested_handles}),
                        "supporting": sorted({key(h) for h in c.supporting_handles}),
                        "unconfirmed": sorted({key(h) for h in c.unconfirmed_handles}),
                    }
                    for c in payload.checks
                )
                result["verifier_version"] = payload.verifier_version
            else:
                raise ValueError("agent_progress_missing_validated_result")
        action_hash, result_hash = canonical_hash(params), canonical_hash(result)
        same = action_hash == self._state.action_sha256 and result_hash == self._state.result_sha256
        self._state = ProgressCheckpoint(
            action_sha256=action_hash,
            result_sha256=result_hash,
            consecutive=self._state.consecutive + 1 if same else 1,
        )
        return self._state
