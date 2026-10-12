"""Shared label query test support; no collected test cases."""

from __future__ import annotations

from medops.skills.registry import SkillContext
from tests.support.harness import make_deps
from tests.support.harness_data import user, versions

INPUT = {"product": "拔痛酸錠", "question": "6至12歲兒童口服劑量如何給予？"}


ANSWER = {"claims": [{"text": "6 至 12 歲孩童口服 100 mg，一天三次。", "citation_chunk_ids": ["c1"]}]}


def ctx(retrieval, gateway, doc_types, reg, u=None):
    return SkillContext(
        user=u or user(),
        versions=versions().model_copy(update={"skill_version_set": reg.version_set()}),
        deps=make_deps(retrieval, gateway),
        evidence_lookup=lambda _u, _ids: (),
        doc_type_lookup=lambda _u, ids: {d: doc_types[d] for d in ids if d in doc_types},
        trace_id="b" * 32,
        run_id="b" * 32,
    )
