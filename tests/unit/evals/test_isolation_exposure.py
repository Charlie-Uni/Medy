import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest
from pydantic import ValidationError

from medops.evals.isolation import exposure
from medops.evals.isolation.contracts import IsolationError, LedgerHead
from medops.evals.isolation.exposure import append_event, exposure_status, read_ledger
from tests.support.eval_isolation import GOLD_CANARY, QUERY_CANARY, event, uid


def test_round_trip_is_metadata_only_pinned_and_private_file(tmp_path):
    path = tmp_path / "exposure.jsonl"
    first = append_event(path, event(), expected=LedgerHead(sequence=0))
    second = append_event(path, event(2), expected=first)
    entries = read_ledger(path, expected=second)
    assert [item.sequence for item in entries] == [1, 2]
    assert entries[1].previous_sha256 == first.sha256 and entries[1].sha256 == second.sha256
    assert entries[0].event == event()
    assert path.stat().st_mode & 0o777 == 0o600
    assert GOLD_CANARY not in path.read_text() and QUERY_CANARY not in path.read_text()


@pytest.mark.parametrize("change", ["content", "truncate", "remove", "reorder", "duplicate_key", "broken_line"])
def test_tamper_or_missing_history_refuses_pinned_read(tmp_path, change):
    path = tmp_path / "exposure.jsonl"
    first = append_event(path, event(), expected=LedgerHead(sequence=0))
    head = append_event(path, event(2), expected=first)
    lines = path.read_bytes().splitlines(keepends=True)
    if change == "content":
        value = json.loads(lines[0])
        value["event"]["role"] = "custodian"
        path.write_text(json.dumps(value) + "\n" + lines[1].decode())
    elif change == "truncate":
        path.write_bytes(lines[0])
    elif change == "remove":
        path.unlink()
    elif change == "reorder":
        path.write_bytes(lines[1] + lines[0])
    elif change == "duplicate_key":
        path.write_bytes(lines[0].replace(b'{"event":', b'{"sequence":1,"event":', 1) + lines[1])
    else:
        path.write_bytes(b'{"gold":"' + GOLD_CANARY.encode() + b'"}')
    with pytest.raises(IsolationError) as error:
        read_ledger(path, expected=head)
    assert GOLD_CANARY not in str(error.value)


def test_stale_head_and_duplicate_event_do_not_append(tmp_path):
    path = tmp_path / "exposure.jsonl"
    initial = LedgerHead(sequence=0)
    head = append_event(path, event(), expected=initial)
    original = path.read_bytes()
    with pytest.raises(IsolationError, match="^ledger_head_changed$"):
        append_event(path, event(2), expected=initial)
    with pytest.raises(IsolationError, match="^duplicate_event$"):
        append_event(path, event(), expected=head)
    assert path.read_bytes() == original


def test_concurrent_writers_have_one_winner_and_no_overwrite(tmp_path):
    path = tmp_path / "exposure.jsonl"
    initial = LedgerHead(sequence=0)

    def write(value):
        try:
            return append_event(path, event(value), expected=initial)
        except IsolationError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(write, (1, 2)))
    heads = [item for item in results if isinstance(item, LedgerHead)]
    assert len(heads) == 1 and results.count("ledger_head_changed") == 1
    assert len(read_ledger(path, expected=heads[0])) == 1


def test_no_record_remains_unknown_and_only_relevant_optimization_exposure_counts(tmp_path):
    path = tmp_path / "exposure.jsonl"
    assert exposure_status((), collection_id=uid(101)) == "unknown"
    head = append_event(path, event(role="runtime"), expected=LedgerHead(sequence=0))
    assert exposure_status(read_ledger(path, expected=head), collection_id=uid(101)) == "unknown"
    head = append_event(path, event(2), expected=head)
    entries = read_ledger(path, expected=head)
    assert exposure_status(entries, collection_id=uid(101)) == "exposed"
    assert exposure_status(entries, collection_id=uid(999)) == "unknown"
    assert exposure_status(entries, collection_id=uid(999), family_ids=(uid(1001),)) == "exposed"


@pytest.mark.parametrize("dangling", [False, True])
def test_symlink_read_and_write_refuse_without_touching_target(tmp_path, dangling):
    target = tmp_path / "target"
    if not dangling:
        target.write_text("UNCHANGED")
    link = tmp_path / "link"
    link.symlink_to(target)
    with pytest.raises(IsolationError, match="^ledger_io$"):
        read_ledger(link, expected=LedgerHead(sequence=0))
    with pytest.raises(IsolationError, match="^ledger_io$"):
        append_event(link, event(), expected=LedgerHead(sequence=0))
    assert not target.exists() if dangling else target.read_text() == "UNCHANGED"


def test_limits_and_bad_file_fail_closed(tmp_path, monkeypatch):
    path = tmp_path / "ledger"
    monkeypatch.setattr(exposure, "MAX_LEDGER_BYTES", 8)
    with pytest.raises(IsolationError, match="^ledger_limit$"):
        append_event(path, event(), expected=LedgerHead(sequence=0))
    assert path.read_bytes() == b""
    path.write_bytes(b"x" * 9)
    with pytest.raises(IsolationError, match="^ledger_limit$"):
        read_ledger(path, expected=LedgerHead(sequence=0))
    with pytest.raises(IsolationError, match="^ledger_io$"):
        read_ledger(tmp_path, expected=LedgerHead(sequence=0))


def test_sync_failure_preserves_uncertain_event_and_never_silently_retries(tmp_path, monkeypatch):
    path = tmp_path / "exposure.jsonl"
    initial = LedgerHead(sequence=0)

    def fail(fd):
        raise OSError("PRIVATE IO MESSAGE")

    monkeypatch.setattr(exposure.os, "fsync", fail)
    with pytest.raises(IsolationError, match="^ledger_io$") as error:
        append_event(path, event(), expected=initial)
    assert "PRIVATE IO MESSAGE" not in str(error.value)
    assert path.stat().st_size > 0
    with pytest.raises(IsolationError, match="^ledger_head_changed$"):
        append_event(path, event(2), expected=initial)


def test_naive_time_and_unmatched_head_metadata_rejected():
    with pytest.raises(ValidationError):
        type(event())(**{**event().model_dump(), "occurred_at": datetime(2026, 10, 12)})
    with pytest.raises(ValidationError):
        LedgerHead(sequence=1)


def test_unvalidated_event_and_head_refuse_before_creating_file(tmp_path):
    path = tmp_path / "ledger"
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        append_event(path, event().model_copy(update={"role": GOLD_CANARY}), expected=LedgerHead(sequence=0))
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        append_event(path, event(), expected=LedgerHead(sequence=0).model_copy(update={"sequence": -1}))
    assert not path.exists()


@pytest.mark.parametrize("role", ["runtime", "validator", "custodian"])
def test_candidate_generation_purpose_is_exposure_regardless_of_role(tmp_path, role):
    path = tmp_path / "ledger"
    value = event(role=role).model_copy(update={"purpose": "candidate_generation"})
    head = append_event(path, value, expected=LedgerHead(sequence=0))
    assert exposure_status(read_ledger(path, expected=head), collection_id=uid(101)) == "exposed"


def test_existing_public_ledger_is_refused_without_appending_or_chmod(tmp_path):
    path = tmp_path / "ledger"
    head = append_event(path, event(), expected=LedgerHead(sequence=0))
    original = path.read_bytes()
    path.chmod(0o644)
    with pytest.raises(IsolationError, match="^ledger_io$"):
        read_ledger(path, expected=head)
    with pytest.raises(IsolationError, match="^ledger_io$"):
        append_event(path, event(2), expected=head)
    assert path.read_bytes() == original and path.stat().st_mode & 0o777 == 0o644
