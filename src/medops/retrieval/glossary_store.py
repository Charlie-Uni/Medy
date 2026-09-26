"""Versioned glossary files (ADR-0008, record 93).

A glossary lives at `<GLOSSARY_DIR>/<version>.json` where `version = glossary-<YYYYMMDD>-<sha12>` and `sha12` is the
first twelve hex digits of the SHA-256 of the canonical JSON of the entries — the same digest the build tool
computes, so a file whose content drifted from its name is refused. `glossary-none` is the released default and
means "no glossary" (the rewriter then yields the single normalized query). The released policy names the version
(`retrieval_params/hybrid` key `glossary`); the runtime loads and verifies it here and fails closed when the file is
missing or does not match, because a silently different glossary would change retrieval under an unchanged
`retrieval_version`.
"""

from __future__ import annotations

import re
from pathlib import Path

from medops.core.canonical import canonical_hash
from medops.core.errors import ErrorCode, InfrastructureError
from medops.retrieval.rewrite import GLOSSARY_NONE, Glossary, GlossaryEntry, load_glossary

GLOSSARY_VERSION_RE = re.compile(r"^glossary-(?:none|\d{8}-[0-9a-f]{12})$")


def glossary_digest(entries: tuple[GlossaryEntry, ...] | list[GlossaryEntry]) -> str:
    """SHA-256 hex of the canonical JSON of the entries (the build tool's version suffix takes the first 12)."""
    return canonical_hash([e.model_dump(mode="json") for e in entries])


def glossary_version_for(entries: tuple[GlossaryEntry, ...] | list[GlossaryEntry], built_on: str) -> str:
    """`built_on` is YYYYMMDD."""
    return f"glossary-{built_on}-{glossary_digest(entries)[:12]}"


def valid_glossary_version(version: str) -> bool:
    return bool(GLOSSARY_VERSION_RE.match(version))


def load_versioned_glossary(directory: Path | str | None, version: str) -> Glossary | None:
    """None for `glossary-none`; otherwise the verified glossary, or an infrastructure error (503 in the API) when the
    deployment lacks the directory or the file, or the file's version / digest disagree with the requested version."""
    if version == GLOSSARY_NONE:
        return None
    if not valid_glossary_version(version):
        raise InfrastructureError(
            ErrorCode.dependency_unavailable, detail=f"invalid glossary version {version!r}", retryable=False
        )
    if not directory:
        raise InfrastructureError(
            ErrorCode.dependency_unavailable,
            detail="a glossary is released but GLOSSARY_DIR is not configured",
            retryable=False,
        )
    path = Path(directory) / f"{version}.json"
    if not path.is_file():
        raise InfrastructureError(
            ErrorCode.dependency_unavailable, detail=f"glossary file missing: {path.name}", retryable=False
        )
    try:
        glossary = load_glossary(path)
    except Exception as exc:  # noqa: BLE001 - any parse / validation failure is a deployment fault
        raise InfrastructureError(
            ErrorCode.dependency_unavailable, detail=f"glossary file invalid: {path.name}: {exc}", retryable=False
        ) from exc
    if glossary.version != version:
        raise InfrastructureError(
            ErrorCode.dependency_unavailable,
            detail=f"glossary file {path.name} declares version {glossary.version}",
            retryable=False,
        )
    expected = version.rsplit("-", 1)[-1]
    if glossary_digest(glossary.entries)[:12] != expected:
        raise InfrastructureError(
            ErrorCode.dependency_unavailable,
            detail=f"glossary file {path.name} content does not match its version digest",
            retryable=False,
        )
    return glossary
