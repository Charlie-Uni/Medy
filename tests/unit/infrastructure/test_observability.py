from __future__ import annotations

import copy
import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr, ValidationError

from medops.core.config import Settings
from medops.core.telemetry import telemetry_options
from medops.infrastructure.observability import (
    LangfuseScores,
    ScoreExportError,
    ScoreQueue,
    ScoreQueueFull,
    feedback_event,
    score_event,
    validate_score_event,
)
from medops.worker import observability as worker

NOW = datetime(2026, 10, 8, tzinfo=UTC)


def event(**changes):
    base = dict(
        identity="fixture-1",
        trace_id="a" * 32,
        name="metric",
        value=True,
        timestamp=NOW,
        metadata={"source": "rule", "formal_gate": False},
    )
    return score_event(**{**base, **changes})


def sender(handler):
    def transport(request):
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"traceId": request.url.params["traceId"]}]})
        return handler(request)

    return LangfuseScores("http://localhost:3030", "pk-fixture", "sk-fixture", transport=httpx.MockTransport(transport))


def ack(request):
    sent = json.loads(request.content)["batch"][0]
    return httpx.Response(207, json={"successes": [{"id": sent["id"], "status": 201}], "errors": []})


def test_feedback_is_categorical_and_never_exports_correction_or_principal():
    e = feedback_event(
        {
            "feedback_id": "f1",
            "trace_id": "a" * 32,
            "signal": "correction",
            "created_at": NOW,
            "correction_text": "PRIVATE_MEDICAL_TEXT",
            "principal": "PRIVATE_PERSON",
        },
        fact_plane="db-hash",
    )
    assert e["body"]["value"] == "correction" and e["body"]["dataType"] == "CATEGORICAL"
    assert "PRIVATE" not in json.dumps(e)
    assert e["body"]["metadata"]["formal_gate"] is False
    validate_score_event(e)


@pytest.mark.parametrize("value", [None, float("nan"), float("inf"), "full free text", [], {}])
def test_missing_and_nonmetric_values_are_rejected(value):
    with pytest.raises(ValueError):
        event(value=value)


@pytest.mark.parametrize("metadata", [{"query": "private"}, {"source": {"nested": "private"}}, {"source": "x" * 301}])
def test_metadata_allowlist_and_bounds(metadata):
    with pytest.raises(ValueError):
        event(metadata=metadata)


def test_wire_payload_is_strict_and_immutable(tmp_path):
    q = ScoreQueue(tmp_path / "state.db", "destination")
    e = event()
    assert q.enqueue(e) and not q.enqueue(e)
    changed = event(value=False)
    assert changed["id"] == e["id"]
    with pytest.raises(ValueError, match="immutable"):
        q.enqueue(changed)
    added = copy.deepcopy(e)
    added["body"]["comment"] = "PRIVATE"
    with pytest.raises(ValueError, match="allowlisted"):
        q.enqueue(added)
    assert (tmp_path / "state.db").stat().st_mode & 0o777 == 0o600
    q.close()


def test_queue_survives_restart_and_acknowledgment_loss(tmp_path):
    calls = []
    current = [datetime(2026, 10, 8, 0, 0, tzinfo=UTC)]

    def clock():
        return current[0]

    def lost_ack(request):
        calls.append(json.loads(request.content))
        raise httpx.ReadTimeout("secret remote details")

    first = sender(lost_ack)
    path = tmp_path / "state.db"
    q = ScoreQueue(path, first.destination, clock=clock)
    q.enqueue(event())
    assert q.drain(first) == {
        "attempted": 1,
        "acknowledged": 0,
        "failed": 1,
        "pending": 1,
        "delayed": 1,
        "dead_lettered": 0,
    }
    assert q.conn.execute("select last_error from scores").fetchone()[0] == "transport_failure"
    q.close()
    first.close()
    current[0] = datetime(2026, 10, 8, 0, 0, 6, tzinfo=UTC)

    def success(request):
        calls.append(json.loads(request.content))
        return ack(request)

    second = sender(success)
    q = ScoreQueue(path, second.destination, clock=clock)
    assert q.drain(second)["acknowledged"] == 1
    assert calls[0] == calls[1]  # fixed event id AND timestamp even after process restart/next day
    assert q.drain(second)["attempted"] == 0
    assert q.conn.execute("select attempts from scores").fetchone()[0] == 2
    q.close()
    second.close()


def test_destination_change_is_rejected(tmp_path):
    path = tmp_path / "state.db"
    q = ScoreQueue(path, "project-a")
    q.close()
    with pytest.raises(ValueError, match="another"):
        ScoreQueue(path, "project-b")


@pytest.mark.parametrize(
    "status,body",
    [
        (401, {"secret": "PRIVATE"}),
        (500, {}),
        (302, {}),
        (207, {"successes": [], "errors": [{"message": "PRIVATE"}]}),
        (200, {"successes": [{"id": "wrong"}], "errors": []}),
    ],
)
def test_rejection_or_partial_response_is_never_acknowledged(status, body):
    client = sender(lambda request: httpx.Response(status, json=body))
    with pytest.raises(ScoreExportError) as exc:
        client.send(event())
    assert "PRIVATE" not in str(exc.value)
    client.close()


def test_failed_event_does_not_prevent_healthy_events_in_same_batch(tmp_path):
    bad = event()
    good = event(identity="second")

    def send(request):
        e = json.loads(request.content)["batch"][0]
        return httpx.Response(500) if e["id"] == bad["id"] else ack(request)

    client = sender(send)
    q = ScoreQueue(tmp_path / "state.db", client.destination)
    q.enqueue(bad)
    q.enqueue(good)
    assert q.drain(client) == {
        "attempted": 2,
        "acknowledged": 1,
        "failed": 1,
        "pending": 1,
        "delayed": 1,
        "dead_lettered": 0,
    }
    q.close()
    client.close()


def settings(**extra):
    return Settings(
        _env_file=None, database_url="postgresql://localhost/test", redis_url="redis://localhost/0", **extra
    )


def test_configuration_targets_both_transports_and_masks_credentials():
    s = settings(
        langfuse_base_url="http://localhost:3030",
        langfuse_public_key="fixture-public",
        langfuse_secret_key="fixture-secret",
    )
    options = telemetry_options(s)
    assert options["endpoint"] == "http://localhost:3030/api/public/otel"
    assert "x-langfuse-ingestion-version=4" in options["headers"]
    assert "fixture-secret" not in s.model_dump_json() and "fixture-public" not in repr(s)


@pytest.mark.parametrize(
    "extra",
    [
        {"langfuse_base_url": "http://localhost:3030"},
        {"langfuse_base_url": "http://remote.example"},
        {"langfuse_base_url": "https://user:pass@remote.example"},
        {"otel_exporter_otlp_endpoint": "http://other:4318"},
        {"otel_exporter_otlp_headers": "Authorization=manual"},
    ],
)
def test_partial_or_conflicting_configuration_rejected(extra):
    config = dict(langfuse_base_url="http://localhost:3030", langfuse_public_key="pk", langfuse_secret_key="sk")
    if len(extra) == 1 and extra.get("langfuse_base_url") == "http://localhost:3030":
        config = {}
    with pytest.raises(ValidationError):
        settings(**{**config, **extra})


def test_sender_preserves_auth_and_does_not_follow_redirects():
    seen = []

    def handler(request):
        seen.append(request)
        return ack(request)

    client = sender(handler)
    client.send(event())
    assert seen[0].url.path == "/api/public/ingestion"
    assert seen[0].headers["Authorization"].startswith("Basic ")
    client.close()


def test_shutdown_stops_before_next_http_attempt(tmp_path):
    client = sender(ack)
    q = ScoreQueue(tmp_path / "state.db", client.destination)
    q.enqueue(event())
    assert q.drain(client, cancelled=lambda: True) == {
        "attempted": 0,
        "acknowledged": 0,
        "failed": 0,
        "pending": 1,
        "delayed": 0,
        "dead_lettered": 0,
    }
    q.close()
    client.close()


@pytest.mark.parametrize("data", [[], [{"traceId": "b" * 32}], None])
def test_absent_or_wrong_trace_prevents_orphan_score(data):
    seen = []

    def transport(request):
        seen.append(request)
        return httpx.Response(200, json={"data": data})

    client = LangfuseScores(
        "http://localhost:3030", "pk-fixture", "sk-fixture", transport=httpx.MockTransport(transport)
    )
    with pytest.raises(ScoreExportError, match="trace_not_visible"):
        client.send(event())
    assert len(seen) == 1 and seen[0].method == "GET"
    assert seen[0].url.params["fields"] == "core"
    client.close()


def test_queue_is_bounded_and_reclaims_delivered_receipts(tmp_path):
    client = sender(ack)
    q = ScoreQueue(tmp_path / "state.db", client.destination, max_rows=2)
    first = event(identity="first")
    q.enqueue(first)
    q.enqueue(event(identity="second"))
    with pytest.raises(ScoreQueueFull, match="capacity"):
        q.enqueue(event(identity="third"))
    assert q.drain(client, limit=1)["acknowledged"] == 1
    assert q.enqueue(event(identity="third"))
    assert q.conn.execute("select count(*) from scores").fetchone()[0] == 2
    q.close()
    client.close()


def test_retry_limit_dead_letters_and_operator_can_requeue(tmp_path):
    now = datetime(2026, 10, 8, tzinfo=UTC)
    client = sender(lambda _request: httpx.Response(500))
    q = ScoreQueue(
        tmp_path / "state.db",
        client.destination,
        max_attempts=1,
        clock=lambda: now,
    )
    e = event()
    q.enqueue(e)
    assert q.drain(client)["dead_lettered"] == 1
    assert q.drain(client)["attempted"] == 0
    assert q.requeue(e["id"])
    assert q.conn.execute("select attempts,dead_lettered_at from scores").fetchone() == (0, None)
    q.close()
    client.close()


def test_old_pending_score_expires_without_http_attempt(tmp_path):
    current = [datetime(2026, 10, 8, tzinfo=UTC)]
    client = sender(ack)
    q = ScoreQueue(tmp_path / "state.db", client.destination, max_age_s=60, clock=lambda: current[0])
    q.enqueue(event())
    current[0] = datetime(2026, 10, 8, 0, 1, 1, tzinfo=UTC)
    result = q.drain(client)
    assert result["attempted"] == 0 and result["dead_lettered"] == 1 and result["pending"] == 0
    assert q.conn.execute("select last_error from scores").fetchone()[0] == "max_age_exceeded"
    q.close()
    client.close()


def test_score_dead_letter_requeue_cli_exits_without_collection_or_http(tmp_path, monkeypatch, capsys):
    settings = type(
        "Config",
        (),
        {
            "langfuse_base_url": "http://localhost:3030",
            "langfuse_public_key": SecretStr("pk"),
            "langfuse_secret_key": SecretStr("sk"),
            "langfuse_score_queue_max_rows": 10,
            "langfuse_score_queue_max_age_s": 60,
            "langfuse_score_queue_max_attempts": 2,
            "langfuse_score_queue_backoff_base_s": 1,
            "langfuse_score_queue_backoff_max_s": 2,
        },
    )()
    observed = {}

    class Sender:
        destination = "fixture"

        def close(self):
            observed["sender_closed"] = True

    class Queue:
        def __init__(self, *args, **kwargs):
            pass

        def requeue(self, score_id):
            observed["score_id"] = score_id
            return True

        def close(self):
            observed["queue_closed"] = True

    monkeypatch.setattr(worker, "Settings", lambda: settings)
    monkeypatch.setattr(worker, "LangfuseScores", lambda *args, **kwargs: Sender())
    monkeypatch.setattr(worker, "ScoreQueue", Queue)
    assert worker.main(["--queue", str(tmp_path / "scores.db"), "--requeue-score", "score-1"]) == 0
    assert observed == {"score_id": "score-1", "queue_closed": True, "sender_closed": True}
    assert '"requeued": true' in capsys.readouterr().out
