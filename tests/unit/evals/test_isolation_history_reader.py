import hashlib
import os
import time

import pytest

from medops.evals.isolation.contracts import IsolationError
from medops.evals.isolation.history import check_history_coverage, history_plan_digest
from medops.evals.isolation.history_reader import history_limits_digest, scan_sample_file
from tests.support.eval_history_reader import arguments, sample, scan, wire
from tests.support.eval_isolation import GOLD_CANARY, uid


def test_complete_main_file_is_bound_private_projection_without_qualification(tmp_path):
    raw = wire(sample(1), sample(2))
    opts = arguments(raw)
    result = scan(tmp_path, raw, opts)
    assert result.receipt.record_count == len(result.samples) == 2
    assert result.receipt.checked_levels == ("query", "gold", "source")
    assert result.samples[0].gold[0].text == GOLD_CANARY
    assert result.schema_sha256 == opts["expected_schema_sha256"]
    assert result.limits_sha256 == opts["expected_limits_sha256"]
    assert "PUBLIC IGNORED NOTES" not in result.model_dump_json()
    assert "PUBLIC FAKE HUMAN" not in result.model_dump_json()
    coverage = check_history_coverage(
        opts["plan"], (result.receipt,), expected_plan_sha256=opts["expected_plan_sha256"]
    )
    assert coverage.declared_scope_status == "complete" and coverage.qualification == result.qualification == "unknown"
    assert coverage.historical_scope_exhaustive_verified is result.historical_scope_exhaustive_verified is False


def test_existing_probe_schema_is_supported_without_schema_rewriting(tmp_path):
    from pathlib import Path

    raw = wire(sample(1, "pc"))
    opts = arguments(raw)
    opts["schema_bytes"] = (
        Path(__file__).resolve().parents[3] / "evals/probe/precise_clause/schema/probe_sample.schema.json"
    ).read_bytes()
    opts["expected_schema_sha256"] = hashlib.sha256(opts["schema_bytes"]).hexdigest()
    assert scan(tmp_path, raw, opts).samples[0].sample_id == "pc-0001"


@pytest.mark.parametrize("raw", [b"", b" \t\r\n\n"])
def test_explicit_empty_file_has_zero_records_only_after_whole_hash_check(tmp_path, raw):
    result = scan(tmp_path, raw)
    assert result.samples == () and result.receipt.record_count == 0 and result.qualification == "unknown"


def test_lf_crlf_final_record_and_unicode_separator_are_not_dropped(tmp_path):
    first, second = sample(1), sample(2)
    first["query"] = "PUBLIC\u2028SYNTHETIC\u2029QUESTION"
    raw = wire(first).replace(b"\n", b"\r\n") + wire(second).rstrip(b"\n")
    result = scan(tmp_path, raw)
    assert len(result.samples) == 2 and result.samples[0].query == first["query"]


@pytest.mark.parametrize(
    "change",
    [
        "bad_last_json",
        "bad_utf8",
        "duplicate_key",
        "nested_duplicate_key",
        "unknown_field",
        "missing_query",
        "wrong_type",
        "duplicate_id",
        "wrong_gold_id",
        "bad_offsets",
        "key_outside_span",
        "duplicate_gold",
        "surrogate",
        "recursive_json",
    ],
)
def test_bad_record_anywhere_returns_fixed_error_without_partial_receipt_or_body(tmp_path, change):
    row = sample(2)
    tail = wire(row)
    if change == "bad_last_json":
        tail = b'{"query":"' + GOLD_CANARY.encode() + b'"\n'
    elif change == "bad_utf8":
        tail = b"\xff\n"
    elif change == "duplicate_key":
        tail = tail.replace(b'{"sample_id":', b'{"query":"SECRET","query":"SECRET","sample_id":', 1)
    elif change == "nested_duplicate_key":
        tail = tail.replace(b'"page": 1', b'"page": 1, "page": 1')
    elif change == "unknown_field":
        row["hidden_body"] = GOLD_CANARY
    elif change == "missing_query":
        del row["query"]
    elif change == "wrong_type":
        row["required_gold_evidence"][0]["page"] = True
    elif change == "duplicate_id":
        row = sample(1)
    elif change == "wrong_gold_id":
        row["required_gold_evidence"][0]["gold_id"] = "ms-9999-g1"
    elif change == "bad_offsets":
        row["required_gold_evidence"][0]["evidence_span"]["char_end"] += 1
    elif change == "key_outside_span":
        row["required_gold_evidence"][0]["key_text"] = "NOT IN SPAN"
    elif change == "duplicate_gold":
        row["required_gold_evidence"] *= 2
    elif change == "surrogate":
        tail = tail.replace(b"PUBLIC SYNTHETIC QUESTION", b"PUBLIC\\ud800QUESTION")
    elif change == "recursive_json":
        tail = b"[" * 2000 + b"0" + b"]" * 2000
    if change not in {
        "bad_last_json",
        "bad_utf8",
        "duplicate_key",
        "nested_duplicate_key",
        "surrogate",
        "recursive_json",
    }:
        tail = wire(row)
    with pytest.raises(IsolationError, match="^invalid_payload$") as error:
        scan(tmp_path, wire(sample(1)) + tail)
    assert GOLD_CANARY not in str(error.value)
    assert error.value.__suppress_context__ or error.value.__context__ is None


@pytest.mark.parametrize("change", ["file_sha", "plan_sha", "artifact_id", "schema_sha", "limits_sha"])
def test_every_declared_binding_is_checked(tmp_path, change):
    raw = wire(sample())
    opts = arguments(raw)
    if change == "file_sha":
        raw += b"\n"
    elif change == "artifact_id":
        opts["artifact_id"] = uid(99)
    else:
        opts[
            {
                "plan_sha": "expected_plan_sha256",
                "schema_sha": "expected_schema_sha256",
                "limits_sha": "expected_limits_sha256",
            }[change]
        ] = "f" * 64
    with pytest.raises(IsolationError, match="^binding_mismatch$"):
        scan(tmp_path, raw, opts)


@pytest.mark.parametrize("level", ["verdict", "output", "aggregate", "query_only", "different_adapter"])
def test_unsupported_coverage_or_adapter_never_gets_checked(tmp_path, level):
    raw = wire(sample())
    opts = arguments(raw)
    requirement = opts["plan"].requirements[0]
    requirement = requirement.model_copy(
        update={"adapter": "retrieval-fields-v1"}
        if level == "different_adapter"
        else {"required_levels": ("query",) if level == "query_only" else ("query", "gold", "source", level)}
    )
    opts["plan"] = opts["plan"].model_copy(update={"requirements": (requirement,)})
    opts["expected_plan_sha256"] = history_plan_digest(opts["plan"])
    with pytest.raises(IsolationError, match="^history_unsupported$"):
        scan(tmp_path, raw, opts)


@pytest.mark.parametrize("limit", ["max_file_bytes", "max_line_bytes", "max_records", "max_projected_chars"])
def test_each_explicit_cap_refuses_without_partial_success(tmp_path, limit):
    raw = wire(sample(1), sample(2))
    opts = arguments(raw)
    opts["limits"] = opts["limits"].model_copy(update={limit: 1})
    opts["expected_limits_sha256"] = history_limits_digest(opts["limits"])
    with pytest.raises(IsolationError, match="^history_limit$"):
        scan(tmp_path, raw, opts)


@pytest.mark.parametrize("mode", ["before", "after_first_row", "past_deadline", "callback_error", "callback_not_bool"])
def test_cancel_and_timeout_cannot_emit_a_checked_receipt(tmp_path, monkeypatch, mode):
    import medops.evals.isolation.history_reader as reader

    raw = wire(sample(1), sample(2))
    opts = arguments(raw)
    if mode == "past_deadline":
        opts["deadline"] = time.monotonic() - 1
    elif mode == "callback_error":

        def failed():
            raise RuntimeError(GOLD_CANARY)

        opts["cancelled"] = failed
    elif mode == "callback_not_bool":
        opts["cancelled"] = lambda: GOLD_CANARY
    elif mode == "before":
        opts["cancelled"] = lambda: True
    else:
        stopped = False
        original = reader._sample

        def parsed(row):
            nonlocal stopped
            result = original(row)
            stopped = True
            return result

        monkeypatch.setattr(reader, "_sample", parsed)
        opts["cancelled"] = lambda: stopped
    with pytest.raises(IsolationError, match="^history_interrupted$") as error:
        scan(tmp_path, raw, opts)
    assert GOLD_CANARY not in str(error.value)


def test_arbitrary_schema_cannot_be_admitted_even_with_its_matching_hash(tmp_path):
    raw = wire(sample())
    opts = arguments(raw)
    opts["schema_bytes"] = b'{"type":"object"}'
    opts["expected_schema_sha256"] = hashlib.sha256(opts["schema_bytes"]).hexdigest()
    with pytest.raises(IsolationError, match="^history_unsupported$"):
        scan(tmp_path, raw, opts)


@pytest.mark.parametrize("change", ["world_readable", "closed", "pipe", "directory", "fd_bool"])
def test_only_owned_private_regular_descriptor_is_read(tmp_path, change):
    raw = wire(sample())
    opts = arguments(raw)
    path = tmp_path / "public-synthetic.jsonl"
    path.write_bytes(raw)
    path.chmod(0o600)
    with path.open("rb") as stream:
        fd = stream.fileno()
        close = []
        if change == "world_readable":
            path.chmod(0o644)
        elif change == "closed":
            fd = os.dup(fd)
            os.close(fd)
        elif change == "pipe":
            fd, write = os.pipe()
            close = [fd, write]
        elif change == "directory":
            fd = os.open(tmp_path, os.O_RDONLY)
            close = [fd]
        elif change == "fd_bool":
            fd = True
        try:
            with pytest.raises(
                IsolationError, match="^" + ("invalid_metadata" if change == "fd_bool" else "history_io") + "$"
            ):
                scan_sample_file(fd, **opts)
        finally:
            for extra in close:
                os.close(extra)


def test_pread_preserves_caller_offset_and_does_not_close_descriptor(tmp_path):
    raw = wire(sample())
    opts = arguments(raw)
    path = tmp_path / "public-synthetic.jsonl"
    path.write_bytes(raw)
    path.chmod(0o600)
    with path.open("rb") as stream:
        stream.seek(7)
        result = scan_sample_file(stream.fileno(), **opts)
        assert stream.tell() == 7 and not stream.closed and len(result.samples) == 1


def test_file_mutation_after_validation_is_detected_before_receipt(tmp_path, monkeypatch):
    import medops.evals.isolation.history_reader as reader

    raw = wire(sample())
    opts = arguments(raw)
    original = reader._sample

    def mutate(row):
        result = original(row)
        (tmp_path / "public-synthetic.jsonl").write_bytes(raw + b"\n")
        return result

    monkeypatch.setattr(reader, "_sample", mutate)
    with pytest.raises(IsolationError, match="^binding_mismatch$"):
        scan(tmp_path, raw, opts)


def test_no_answer_source_fields_are_explicit_without_fabricating_gold(tmp_path):
    row = sample()
    row.update(
        answerable=False,
        expected_behaviour="insufficient_evidence",
        slices=["no_answer"],
        required_gold_evidence=[],
        abstention={
            "scope_document_key": "PUBLIC document",
            "topic": "PUBLIC topic",
            "absence_check": "PUBLIC absence check",
            "document_pages": [1, 2],
        },
    )
    result = scan(tmp_path, wire(row)).samples[0]
    assert result.gold == () and result.absence_document_key == "PUBLIC document" and result.absence_pages == (1, 2)


def test_conflict_and_derived_link_are_metadata_not_inferred_families(tmp_path):
    row = sample()
    row.update(
        derived_from="ms-0002",
        slices=["version_conflict"],
        conflict={
            "family_document_keys": ["PUBLIC old", "PUBLIC new"],
            "current_document_key": "PUBLIC new",
            "clause_topic": "PUBLIC topic",
            "synthetic": True,
        },
    )
    result = scan(tmp_path, wire(row)).samples[0]
    assert result.derived_from == "ms-0002" and result.conflict_document_keys == ("PUBLIC old", "PUBLIC new")
    assert result.conflict_synthetic is True


@pytest.mark.parametrize("value", [True, "1000", 0, 33554433])
def test_copied_limits_are_strictly_revalidated(value):
    opts = arguments(b"")
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        history_limits_digest(opts["limits"].model_copy(update={"max_file_bytes": value}))


@pytest.mark.parametrize("deadline", [True, "125", float("nan"), float("inf"), 10**400])
def test_invalid_deadline_metadata_is_rejected_before_io(tmp_path, deadline):
    raw = wire(sample())
    opts = arguments(raw)
    opts["deadline"] = deadline
    with pytest.raises(IsolationError, match="^invalid_metadata$"):
        scan(tmp_path, raw, opts)


def test_file_size_cap_precedes_any_read_or_parse(tmp_path, monkeypatch):
    import medops.evals.isolation.history_reader as reader

    raw = wire(sample())
    opts = arguments(raw)
    opts["limits"] = opts["limits"].model_copy(update={"max_file_bytes": 1})
    opts["expected_limits_sha256"] = history_limits_digest(opts["limits"])

    def forbidden(*args):
        pytest.fail("oversized file must not be read or parsed")

    monkeypatch.setattr(reader.os, "pread", forbidden)
    monkeypatch.setattr(reader, "_sample", forbidden)
    with pytest.raises(IsolationError, match="^history_limit$"):
        scan(tmp_path, raw, opts)


def test_cancel_during_read_and_file_growth_never_produce_receipt(tmp_path, monkeypatch):
    import medops.evals.isolation.history_reader as reader

    raw = wire(sample())
    opts = arguments(raw)
    original = reader.os.pread
    stopped = False

    def read(fd, size, offset):
        nonlocal stopped
        data = original(fd, size, offset)
        stopped = True
        return data

    monkeypatch.setattr(reader.os, "pread", read)
    opts["cancelled"] = lambda: stopped
    with pytest.raises(IsolationError, match="^history_interrupted$"):
        scan(tmp_path, raw, opts)


def test_file_growth_during_capture_fails_binding(tmp_path, monkeypatch):
    import medops.evals.isolation.history_reader as reader

    raw = wire(sample())
    opts = arguments(raw)
    original = reader.os.pread

    def read(fd, size, offset):
        data = original(fd, size, offset)
        if offset == 0:
            (tmp_path / "public-synthetic.jsonl").write_bytes(raw + b"\n")
        return data

    monkeypatch.setattr(reader.os, "pread", read)
    with pytest.raises(IsolationError, match="^binding_mismatch$"):
        scan(tmp_path, raw, opts)


def test_file_hash_checked_before_parsing_records(tmp_path, monkeypatch):
    import medops.evals.isolation.history_reader as reader

    raw = wire(sample())
    opts = arguments(raw)

    def forbidden(*args):
        pytest.fail("changed file must not reach row projection")

    monkeypatch.setattr(reader, "_sample", forbidden)
    with pytest.raises(IsolationError, match="^binding_mismatch$"):
        scan(tmp_path, raw + b"\n", opts)
