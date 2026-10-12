"""Bounded JSONL exposure ledger with advisory locks and externally pinned heads.

Hash chains detect changes against a trusted checkpoint; they are not signatures
or a substitute for custodian permissions/backups. POSIX offline tooling only.
"""

from __future__ import annotations

import fcntl
import os
import stat
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import BinaryIO, Literal
from uuid import UUID

from pydantic import ValidationError

from medops.core.canonical import canonical_hash, canonical_json
from medops.evals.isolation.contracts import (
    ExposureEvent,
    IsolationError,
    LedgerEntry,
    LedgerHead,
    strict_json,
    validated_copy,
)

MAX_LEDGER_BYTES = 16 * 1024 * 1024


@contextmanager
def _open(path: Path, *, write: bool) -> Iterator[BinaryIO]:
    flags = (os.O_RDWR | os.O_CREAT if write else os.O_RDONLY) | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        fd = os.open(path, flags, 0o600)
        with os.fdopen(fd, "r+b" if write else "rb") as stream:
            mode = os.fstat(stream.fileno()).st_mode
            if not stat.S_ISREG(mode) or mode & 0o077:
                raise IsolationError("ledger_io")
            fcntl.flock(stream, fcntl.LOCK_EX if write else fcntl.LOCK_SH)
            try:
                yield stream
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)
    except OSError:
        raise IsolationError("ledger_io") from None


def _entry_hash(sequence: int, previous: str | None, event: ExposureEvent) -> str:
    return canonical_hash({"sequence": sequence, "previous_sha256": previous, "event": event.model_dump(mode="json")})


def _entries(stream: BinaryIO) -> tuple[LedgerEntry, ...]:
    if os.fstat(stream.fileno()).st_size > MAX_LEDGER_BYTES:
        raise IsolationError("ledger_limit")
    raw = stream.read(MAX_LEDGER_BYTES + 1)
    if len(raw) > MAX_LEDGER_BYTES:
        raise IsolationError("ledger_limit")
    if raw and not raw.endswith(b"\n"):
        raise IsolationError("ledger_corrupt")
    values: list[LedgerEntry] = []
    ids: set[UUID] = set()
    previous = None
    try:
        for sequence, line in enumerate(raw.splitlines(), start=1):
            entry = LedgerEntry.model_validate(strict_json(line))
            if (
                entry.sequence != sequence
                or entry.previous_sha256 != previous
                or entry.sha256 != _entry_hash(sequence, previous, entry.event)
                or entry.event.event_id in ids
            ):
                raise IsolationError("ledger_corrupt")
            ids.add(entry.event.event_id)
            values.append(entry)
            previous = entry.sha256
    except (ValidationError, ValueError, UnicodeError, RecursionError):
        raise IsolationError("ledger_corrupt") from None
    return tuple(values)


def _head(entries: Sequence[LedgerEntry]) -> LedgerHead:
    return LedgerHead(sequence=len(entries), sha256=entries[-1].sha256 if entries else None)


def read_ledger(path: Path, *, expected: LedgerHead) -> tuple[LedgerEntry, ...]:
    expected = validated_copy(LedgerHead, expected, code="invalid_metadata")
    try:
        path.lstat()
    except FileNotFoundError:
        if expected.sequence:
            raise IsolationError("ledger_head_changed") from None
        return ()
    except OSError:
        raise IsolationError("ledger_io") from None
    with _open(path, write=False) as stream:
        entries = _entries(stream)
        if _head(entries) != expected:
            raise IsolationError("ledger_head_changed")
        return entries


def append_event(path: Path, event: ExposureEvent, *, expected: LedgerHead) -> LedgerHead:
    expected = validated_copy(LedgerHead, expected, code="invalid_metadata")
    event = validated_copy(ExposureEvent, event, code="invalid_metadata")
    with _open(path, write=True) as stream:
        entries = _entries(stream)
        head = _head(entries)
        if head != expected:
            raise IsolationError("ledger_head_changed")
        if any(entry.event.event_id == event.event_id for entry in entries):
            raise IsolationError("duplicate_event")
        sequence = head.sequence + 1
        digest = _entry_hash(sequence, head.sha256, event)
        entry = LedgerEntry(sequence=sequence, previous_sha256=head.sha256, event=event, sha256=digest)
        encoded = (canonical_json(entry.model_dump(mode="json")) + "\n").encode("utf-8")
        if stream.tell() + len(encoded) > MAX_LEDGER_BYTES:
            raise IsolationError("ledger_limit")
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
        return LedgerHead(sequence=sequence, sha256=digest)


def exposure_status(
    entries: Sequence[LedgerEntry], *, collection_id: UUID, family_ids: tuple[UUID, ...] = ()
) -> Literal["exposed", "unknown"]:
    """Absence of an event cannot certify clean historical exposure or unseen tasks."""
    for entry in entries:
        event = entry.event
        relevant = event.collection_id == collection_id or bool(set(family_ids).intersection(event.family_ids))
        if relevant and (
            event.purpose == "candidate_generation"
            or (event.role in {"developer", "generator"} and set(event.levels) - {"aggregate"})
        ):
            return "exposed"
    return "unknown"
