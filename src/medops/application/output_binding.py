"""Private fact metadata for a stored result; no new evidence bodies in the public Task DTO."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import Field

from medops.domain.common import DocStatus, DocType, DomainModel, Sha256
from medops.domain.evidence import Citation, Evidence
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext

if TYPE_CHECKING:
    from medops.skills.registry import SkillContext


class EvidenceBinding(DomainModel):
    citation: Citation
    evidence_text_hash: Sha256
    chunk_content_hash: Sha256
    status: DocStatus
    historical: bool

    @classmethod
    def observed(cls, evidence: Evidence) -> EvidenceBinding:
        return cls.model_validate(evidence.model_dump(exclude={"text"}))


class EvidenceLookupBinding(DomainModel):
    kind: Literal["evidence"] = "evidence"
    ids: tuple[str, ...]
    evidence: tuple[EvidenceBinding, ...]


class DocTypeLookupBinding(DomainModel):
    kind: Literal["doc_types"] = "doc_types"
    ids: tuple[str, ...]
    doc_types: dict[str, DocType]


LookupBinding = Annotated[EvidenceLookupBinding | DocTypeLookupBinding, Field(discriminator="kind")]


class OutputBinding(DomainModel):
    user: UserContext
    query_context: QueryContext
    evidence: tuple[EvidenceBinding, ...]
    lookups: tuple[LookupBinding, ...] = ()


def observe_lookups(ctx: SkillContext, reads: list[LookupBinding]) -> SkillContext:
    """Bind positive and negative lookup observations without rerunning models or guessing missing facts."""

    def record(read: LookupBinding) -> None:
        assert ctx.deps.audit is not None
        ctx.deps.audit.record_event("fact_lookup", read.model_dump(mode="json"))
        reads.append(read)

    def evidence(user: UserContext, ids: Sequence[str]) -> Sequence[Evidence]:
        found = tuple(ctx.evidence_lookup(user, ids))
        record(EvidenceLookupBinding(ids=tuple(ids), evidence=tuple(EvidenceBinding.observed(e) for e in found)))
        return found

    def doc_types(user: UserContext, ids: Sequence[str]) -> Mapping[str, DocType]:
        found = dict(ctx.doc_type_lookup(user, ids))
        record(DocTypeLookupBinding(ids=tuple(ids), doc_types=found))
        return found

    return replace(ctx, evidence_lookup=evidence, doc_type_lookup=doc_types)
