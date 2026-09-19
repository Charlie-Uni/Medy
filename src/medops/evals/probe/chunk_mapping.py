"""Map frozen probe golds to exported chunk source spans (SPEC section 6).

    python -m medops.evals.probe.chunk_mapping VERSION --pages PAGES \
        --chunks chunks.json --out EXPERIMENT/chunk_mapping.chunker-v1.json

The input snapshot is an object containing `chunker_version`, `normalization`,
`extraction` (extractor, extractor_version, params_hash), and `chunks`. Each chunk
has chunk_id, source_hash, version_label, and nonempty spans containing page,
char_start, char_end. Source spans come from the ingestion export; chunk text is
neither accepted nor searched. Coordinates are Unicode code points in norm-v1.

One same-source, same-version, same-page span must cover the entire unique key.
Separate fragments cannot be concatenated into a hit. A valid mapping is always
complete: unmappable golds retain empty chunk_ids and an explicit miss reason.

Exit 0: artifact published, all golds mapped. Exit 1: artifact published, with
unmappable golds that count as misses. Exit 2: invalid inputs or refused output,
no artifact published. Output must be outside the frozen version directory and
must not already exist; publication is atomic and never overwrites a target.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import secrets
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from medops.core.canonical import canonical_json
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator
from medops.ingestion.chunker import Span
from medops.retrieval.lexical.normalization import NORMALIZATION_VERSION, normalize_text

SCHEMA_DIR = Path(__file__).resolve().parents[4] / "evals/probe/precise_clause/schema"
GENERATOR = "medops.evals.probe.chunk_mapping/v1"
_EXTRACTION_KEYS = {"extractor", "extractor_version", "params_hash"}
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class MappingRefused(ValueError):
    """Invalid inputs or an unsafe output destination; no mapping is published."""


@dataclass(frozen=True)
class ExportedChunk:
    chunk_id: str
    source_hash: str
    version_label: str
    spans: tuple[Span, ...]


class _CachedPages(PageTextProvider):
    """Use the same page view for frozen validation, key location and span checks."""

    def __init__(self, root: Path) -> None:
        super().__init__(root)
        self.cache: dict[tuple[str, int], str | None] = {}

    def page_text(self, source_hash: str, page: int) -> str | None:
        key = (source_hash, page)
        if key not in self.cache:
            self.cache[key] = super().page_text(source_hash, page)
        return self.cache[key]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise MappingRefused(message)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON object property")
        result[key] = value
    return result


def _reject_constant(value: str) -> Any:
    raise MappingRefused("non-finite numbers are not allowed in JSON")


def _json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    except (UnicodeError, ValueError) as exc:
        raise MappingRefused(f"invalid JSON input: {exc}") from exc


def _object(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    _require(isinstance(value, dict) and set(value) == keys, f"{label}: expected exactly {sorted(keys)}")
    return value


def _string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _snapshot(snapshot: Mapping[str, Any], manifest: dict[str, Any]) -> list[ExportedChunk]:
    _object(snapshot, {"chunker_version", "normalization", "extraction", "chunks"}, "chunk snapshot")
    _require(_string(snapshot["chunker_version"]), "chunker_version must be a nonempty string")
    _require(
        snapshot["normalization"] == manifest["normalization"] == NORMALIZATION_VERSION,
        "snapshot normalization differs from the frozen coordinate system",
    )
    extraction = _object(snapshot["extraction"], _EXTRACTION_KEYS, "snapshot extraction")
    _require(
        extraction == {key: manifest["extraction"][key] for key in _EXTRACTION_KEYS},
        "snapshot extraction differs from frozen extractor/version/params_hash",
    )
    _require(isinstance(snapshot["chunks"], list), "snapshot chunks must be an array")
    result = []
    ids = set()
    for index, row in enumerate(snapshot["chunks"]):
        loc = f"chunks/{index}"
        _object(row, {"chunk_id", "source_hash", "version_label", "spans"}, loc)
        cid = row["chunk_id"]
        _require(_string(cid) and cid not in ids, f"{loc}: duplicate or invalid chunk_id")
        ids.add(cid)
        _require(
            isinstance(row["source_hash"], str) and bool(_SHA256.fullmatch(row["source_hash"])),
            f"{loc}: invalid source_hash",
        )
        _require(_string(row["version_label"]), f"{loc}: invalid version_label")
        _require(isinstance(row["spans"], list) and bool(row["spans"]), f"{loc}: spans must be nonempty")
        spans = []
        for ordinal, span in enumerate(row["spans"]):
            _object(span, {"page", "char_start", "char_end"}, f"{loc}/spans/{ordinal}")
            page, start, end = span["page"], span["char_start"], span["char_end"]
            _require(
                type(page) is int and page > 0 and type(start) is int and type(end) is int and 0 <= start < end,
                f"{loc}/spans/{ordinal}: invalid source coordinates",
            )
            parsed = Span(page, start, end)
            _require(parsed not in spans, f"{loc}: duplicate source span")
            spans.append(parsed)
        result.append(ExportedChunk(cid, row["source_hash"], row["version_label"], tuple(spans)))
    return result


def _frozen_inputs(
    version_dir: Path,
    pages: _CachedPages,
    schema_dir: Path,
    approval_records_root: Path | None,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    names = ("manifest.json", "corpus.json", "samples.jsonl", "SHA256SUMS")
    before = {name: (version_dir / name).read_bytes() for name in names}
    validator = ProbeSetValidator(schema_dir, pages, approval_records_root=approval_records_root)
    report = validator.validate(version_dir, mode="frozen")
    _require(
        report.passed,
        "frozen probe validation failed: "
        + "; ".join(f"{finding.rule} {finding.location}: {finding.message}" for finding in report.errors[:5]),
    )
    _require(
        all((version_dir / name).read_bytes() == raw for name, raw in before.items()),
        "frozen input files changed during validation",
    )
    manifest = _json(before["manifest.json"])
    corpus = _json(before["corpus.json"])
    samples = [_json(line) for line in before["samples.jsonl"].splitlines()]
    # These bytes, not a later reread, are the input used to construct the mapping.
    _require(
        manifest["dataset_hash"] == hashlib.sha256(before["SHA256SUMS"]).hexdigest(), "frozen dataset hash mismatch"
    )
    return manifest, corpus, samples


def build_mapping(
    version_dir: Path,
    pages_dir: Path,
    snapshot: Mapping[str, Any],
    *,
    schema_dir: Path = SCHEMA_DIR,
    generated_at: str | None = None,
    approval_records_root: Path | None = None,
) -> dict[str, Any]:
    """Return a complete schema-valid mapping; annotation/input defects raise MappingRefused.

    Extra source objects or document versions in an export cannot match a gold.
    Coordinates for known corpus sources are additionally checked against page bounds.
    An empty, otherwise valid chunk export yields explicit misses for every gold.
    """
    version_dir = Path(version_dir)
    pages = _CachedPages(Path(pages_dir))
    manifest, corpus, samples = _frozen_inputs(version_dir, pages, Path(schema_dir), approval_records_root)
    chunks = _snapshot(snapshot, manifest)
    docs = {doc["source_hash"]: doc for doc in corpus["documents"]}
    indexed: dict[tuple[str, str, int], list[tuple[str, Span]]] = {}
    for chunk in chunks:
        doc = docs.get(chunk.source_hash)
        for span in chunk.spans:
            if doc is not None:
                _require(span.page <= doc["pages"], f"{chunk.chunk_id}: source page exceeds corpus page count")
                text = pages.page_text(chunk.source_hash, span.page)
                _require(text is not None, f"{chunk.chunk_id}: source page text is missing")
                _require(
                    span.char_end <= len(text or ""), f"{chunk.chunk_id}: source span exceeds normalized page bounds"
                )
            indexed.setdefault((chunk.source_hash, chunk.version_label, span.page), []).append((chunk.chunk_id, span))
    entries = []
    seen = set()
    for sample in samples:
        for gold in sample["required_gold_evidence"]:
            gid = gold["gold_id"]
            _require(gid not in seen, f"duplicate gold_id {gid}")
            seen.add(gid)
            text = pages.page_text(gold["source_hash"], gold["page"])
            _require(text is not None, f"{gid}: gold page text missing")
            assert text is not None
            key = gold["key_text"]
            start = text.find(key)
            _require(
                key == normalize_text(key) and start >= 0 and text.find(key, start + 1) < 0,
                f"{gid}: key_text must occur exactly once, including overlapping occurrences; annotation needs a new version",
            )
            end = start + len(key)
            candidates = indexed.get((gold["source_hash"], gold["version_label"], gold["page"]), [])
            matched = sorted({cid for cid, span in candidates if span.char_start <= start and span.char_end >= end})
            entries.append(
                {
                    "gold_id": gid,
                    "status": "mapped" if matched else "unmappable",
                    "chunk_ids": matched,
                    "reason": None
                    if matched
                    else "No single same-source/version/page chunk span covers the unique key interval; counts as a miss.",
                }
            )
    result = {
        "dataset_version": manifest["dataset_version"],
        "dataset_hash": manifest["dataset_hash"],
        "chunker_version": snapshot["chunker_version"],
        "extraction": dict(snapshot["extraction"]),
        "normalization": snapshot["normalization"],
        "generated_at": generated_at
        if generated_at is not None
        else dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "generator": GENERATOR,
        "entries": sorted(entries, key=lambda entry: entry["gold_id"]),
    }
    schema = _json((Path(schema_dir) / "chunk_mapping.schema.json").read_bytes())
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(result))
    _require(not errors, "generated mapping violates chunk_mapping.schema.json")
    return result


_DIRECTORY_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


def _identity(fd: int) -> tuple[int, int]:
    stat = os.fstat(fd)
    return stat.st_dev, stat.st_ino


def _assert_outside_directory(fd: int, protected: tuple[int, int]) -> None:
    """Check actual opened-directory ancestry, including a directory renamed after open."""
    ancestor = os.dup(fd)
    seen: set[tuple[int, int]] = set()
    try:
        while True:
            identity = _identity(ancestor)
            _require(identity != protected, "output directory is inside the protected directory")
            _require(identity not in seen and len(seen) < 1024, "output directory ancestry changed during validation")
            seen.add(identity)
            parent = os.open("..", _DIRECTORY_FLAGS, dir_fd=ancestor)
            os.close(ancestor)
            ancestor = parent
            if _identity(ancestor) == identity:
                return
    finally:
        os.close(ancestor)


def _open_directory(path: Path, *, create: bool = False, protected: tuple[int, int] | None = None) -> int:
    """Walk a canonical absolute path without following any newly inserted symlink."""
    fd = os.open(path.anchor, _DIRECTORY_FLAGS)
    try:
        for component in path.parts[1:]:
            try:
                child = os.open(component, _DIRECTORY_FLAGS, dir_fd=fd)
            except FileNotFoundError:
                if not create:
                    raise
                assert protected is not None
                _assert_outside_directory(fd, protected)
                try:
                    os.mkdir(component, dir_fd=fd)
                except FileExistsError:
                    pass  # The subsequent O_NOFOLLOW open validates a concurrent creator.
                child = os.open(component, _DIRECTORY_FLAGS, dir_fd=fd)
            os.close(fd)
            fd = child
            if protected is not None:
                _require(_identity(fd) != protected, "output directory is inside the protected directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _validate_parent_binding(fd: int, requested: Path, canonical: Path, protected: tuple[int, int]) -> None:
    _assert_outside_directory(fd, protected)
    _require(requested.resolve() == canonical, "output parent path changed during publication")
    current = _open_directory(canonical)
    try:
        _require(_identity(current) == _identity(fd), "output parent directory changed during publication")
    finally:
        os.close(current)


def publish_artifact(raw: bytes, out: Path, *, protected_dir: Path) -> None:
    """Publish complete bytes exclusively, with all mutations bound to a checked directory FD.

    Existing parent symlinks are resolved before opening; subsequent symlink substitution
    is refused. The protected directory must exist. This POSIX helper is also used by
    experiment exporters so they share the mapping publisher's output safeguards.
    """
    out = Path(out).absolute()
    _require(bool(out.name), "output must name a file")
    try:
        protected_path = Path(protected_dir).resolve(strict=True)
        parent_path = out.parent.resolve()
    except RuntimeError as exc:
        raise MappingRefused("output or protected directory contains a symbolic-link loop") from exc
    _require(
        not (parent_path / out.name).is_relative_to(protected_path), "output must be outside the protected directory"
    )
    protected_fd = _open_directory(protected_path)
    try:
        protected_identity = _identity(protected_fd)
        parent_fd = _open_directory(parent_path, create=True, protected=protected_identity)
        try:
            _validate_parent_binding(parent_fd, out.parent, parent_path, protected_identity)
            try:
                os.stat(out.name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise MappingRefused("output already exists; choose a new experiment path")
            temporary = f".probe-artifact-{secrets.token_hex(16)}.tmp"
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=parent_fd)
            temporary_identity = _identity(fd)
            published = False
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                _validate_parent_binding(parent_fd, out.parent, parent_path, protected_identity)
                # link() is an exclusive atomic create, even if another writer won the race.
                os.link(temporary, out.name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd, follow_symlinks=False)
                published = True
                _validate_parent_binding(parent_fd, out.parent, parent_path, protected_identity)
            except BaseException:
                if published:
                    try:
                        stat = os.stat(out.name, dir_fd=parent_fd, follow_symlinks=False)
                        if (stat.st_dev, stat.st_ino) == temporary_identity:
                            os.unlink(out.name, dir_fd=parent_fd)
                    except FileNotFoundError:
                        pass
                raise
            finally:
                os.unlink(temporary, dir_fd=parent_fd)
        finally:
            os.close(parent_fd)
    finally:
        os.close(protected_fd)


def publish_mapping(mapping: Mapping[str, Any], out: Path, *, version_dir: Path) -> None:
    """Atomically create a new experiment artifact, never replacing a file or frozen input."""
    publish_artifact((canonical_json(mapping) + "\n").encode("utf-8"), out, protected_dir=version_dir)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("version_dir", type=Path)
    parser.add_argument("--pages", required=True, type=Path)
    parser.add_argument("--chunks", required=True, type=Path, help="exported source-span snapshot JSON; no chunk text")
    parser.add_argument("--out", required=True, type=Path, help="new artifact path outside the frozen version")
    parser.add_argument("--schema-dir", type=Path, default=SCHEMA_DIR)
    parser.add_argument("--approval-records-root", type=Path, default=None)
    args = parser.parse_args(argv)
    try:
        snapshot = _json(args.chunks.read_bytes())
        mapping = build_mapping(
            args.version_dir,
            args.pages,
            snapshot,
            schema_dir=args.schema_dir,
            approval_records_root=args.approval_records_root,
        )
        publish_mapping(mapping, args.out, version_dir=args.version_dir)
    except (OSError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    missing = [entry for entry in mapping["entries"] if entry["status"] == "unmappable"]
    print(f"wrote {args.out}: {len(mapping['entries']) - len(missing)} mapped, {len(missing)} unmappable (miss)")
    for entry in missing:
        print(f"MISS {entry['gold_id']}: {entry['reason']}")
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
