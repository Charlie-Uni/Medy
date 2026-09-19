"""Draft-only canonical rewrite of probe JSONL files (M1-01 companion tool; SPEC section 2, PR-01, PR-02).

    python -m medops.evals.probe.canonicalize <version_dir> [--check] [--pages DIR] [--schema-dir DIR]

Rewrites `samples.jsonl` and, when present, `acl_probes.jsonl` into the form the validator requires:
UTF-8 without BOM, LF, no blank lines, trailing newline, one canonical JSON object per line, ordered
by `sample_id` / `probe_id`. Only the byte representation and the record order change; the set of
records is unchanged, and the tool re-verifies that before publishing. It never touches
manifest.json, corpus.json, review_prompt.md, mappings/ or SHA256SUMS, and it never "fixes" gold
content: anything that is not a plain representation problem is refused and left to the annotator.

Refusals (exit 2, nothing written): the directory is not a draft (manifest `status` is not `draft`,
`frozen_at` is set, or SHA256SUMS exists), manifest unreadable, a line is not a JSON object, a line
holds duplicate keys or NaN/Infinity, a record lacks its id or ids repeat. All files are parsed and
checked before the first byte is written, and each file is published atomically. After a rewrite the
validator runs in draft mode: exit 0 when it passes, 1 when it reports errors. `--check` writes
nothing and exits 1 when any file would change.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from medops.core.canonical import canonical_json
from medops.evals.probe.validator import PageTextProvider, ProbeSetValidator

JSONL_FILES: tuple[tuple[str, str], ...] = (("samples.jsonl", "sample_id"), ("acl_probes.jsonl", "probe_id"))
EXIT_OK, EXIT_VALIDATION_FAILED, EXIT_REFUSED = 0, 1, 2


class RefusedError(Exception):
    """The rewrite was refused before any write; the message says why."""


@dataclass(frozen=True)
class FileResult:
    name: str
    records: int
    changed: bool
    reordered: bool


def _reject_constant(name: str) -> Any:
    raise ValueError(f"{name} is not allowed in JSON")


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate key {key!r}")
        obj[key] = value
    return obj


def _parse_lines(path: Path) -> list[dict[str, Any]]:
    """Tolerant read of the things this tool repairs (BOM, CR/CRLF, blank lines); strict on content."""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RefusedError(f"{path.name}: not valid UTF-8 at byte {exc.start}") from exc
    # Only CR/LF are line breaks here; str.splitlines would also split on U+2028 etc., which may
    # legitimately appear inside a JSON string.
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    records: list[dict[str, Any]] = []
    for lineno, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line, object_pairs_hook=_reject_duplicate_keys, parse_constant=_reject_constant)
        except ValueError as exc:  # JSONDecodeError is a ValueError
            raise RefusedError(f"{path.name}:{lineno}: {exc}") from exc
        if not isinstance(obj, dict):
            raise RefusedError(f"{path.name}:{lineno}: line is not a JSON object")
        records.append(obj)
    return records


def _ordered(records: list[dict[str, Any]], id_key: str, name: str) -> tuple[list[dict[str, Any]], bool]:
    ids: list[str] = []
    for index, record in enumerate(records, start=1):
        value = record.get(id_key)
        if not isinstance(value, str) or not value:
            raise RefusedError(f"{name}: record {index} has no string {id_key}")
        ids.append(value)
    duplicates = sorted(value for value, count in Counter(ids).items() if count > 1)
    if duplicates:
        raise RefusedError(f"{name}: duplicate {id_key} {duplicates}")
    ordered = sorted(records, key=lambda record: str(record[id_key]))
    return ordered, [record[id_key] for record in ordered] != ids


def _canonical_bytes(records: list[dict[str, Any]], name: str) -> bytes:
    try:
        return "".join(canonical_json(record) + "\n" for record in records).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise RefusedError(f"{name}: not canonicalizable: {exc}") from exc


def _assert_same_records(before: list[dict[str, Any]], data: bytes, name: str) -> None:
    after = [json.loads(line) for line in data.decode("utf-8").split("\n")[:-1]]
    if sorted(canonical_json(r) for r in before) != sorted(canonical_json(r) for r in after):
        raise RefusedError(f"{name}: internal check failed, record set would change; nothing written")


def _assert_draft(version_dir: Path) -> None:
    manifest_path = version_dir / "manifest.json"
    if not manifest_path.is_file():
        raise RefusedError("manifest.json missing")
    try:
        manifest = json.loads(manifest_path.read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise RefusedError(f"manifest.json unreadable: {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("status") != "draft":
        raise RefusedError("manifest status is not draft; frozen directories are immutable")
    if manifest.get("frozen_at") is not None:
        raise RefusedError("manifest frozen_at is set; frozen directories are immutable")
    if (version_dir / "SHA256SUMS").exists():
        raise RefusedError("SHA256SUMS present; the directory is frozen or being frozen")


def _publish(path: Path, data: bytes) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def canonicalize(version_dir: Path, *, check: bool = False) -> list[FileResult]:
    """Plan the rewrite for every JSONL file and, unless `check`, publish the changed ones.
    Raises RefusedError before anything is written."""
    version_dir = Path(version_dir)
    _assert_draft(version_dir)
    plan: list[tuple[Path, bytes, FileResult]] = []
    for name, id_key in JSONL_FILES:
        path = version_dir / name
        if not path.is_file():
            if name == "samples.jsonl":
                raise RefusedError("samples.jsonl missing")
            continue
        records = _parse_lines(path)
        ordered, reordered = _ordered(records, id_key, name)
        data = _canonical_bytes(ordered, name)
        _assert_same_records(records, data, name)
        plan.append((path, data, FileResult(name, len(ordered), data != path.read_bytes(), reordered)))
    for path, data, result in plan:  # every file was parsed and checked before the first write
        if result.changed and not check:
            _publish(path, data)
    return [result for _, _, result in plan]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="medops.evals.probe.canonicalize")
    parser.add_argument("version_dir", type=Path)
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 if any file would change")
    parser.add_argument(
        "--pages", type=Path, default=None, help="<dir>/<source_hash>/<page>.txt for the draft validation"
    )
    parser.add_argument("--schema-dir", type=Path, default=Path("evals/probe/precise_clause/schema"))
    args = parser.parse_args(argv)
    try:
        results = canonicalize(args.version_dir, check=args.check)
    except RefusedError as exc:
        print(f"REFUSED: {exc}")
        return EXIT_REFUSED
    for r in results:
        state = ("would rewrite" if args.check else "rewritten") if r.changed else "unchanged"
        print(f"{r.name}: {state} ({r.records} records{', reordered' if r.reordered else ''})")
    if args.check:
        return EXIT_VALIDATION_FAILED if any(r.changed for r in results) else EXIT_OK
    validator = ProbeSetValidator(args.schema_dir, PageTextProvider(args.pages) if args.pages else None)
    report = validator.validate(args.version_dir, mode="draft")
    for f in report.findings:
        print(f"[{f.level.upper():7}] {f.rule} {f.location}: {f.message}")
    print(
        f"{'PASS' if report.passed else 'FAIL'} (draft); errors={len(report.errors)} warnings={len(report.findings) - len(report.errors)}"
    )
    return EXIT_OK if report.passed else EXIT_VALIDATION_FAILED


if __name__ == "__main__":
    sys.exit(main())
