import io
import json
import logging

from medops.core.logging import REDACTED, JsonFormatter, configure_logging, get_logger, redact
from medops.core.tracing import bind_trace_id


def _capture(level: str = "INFO") -> tuple[io.StringIO, logging.Logger]:
    stream = io.StringIO()
    configure_logging(level, stream=stream)
    return stream, get_logger("medops.test")


def test_log_line_is_json_with_fixed_keys_and_trace_id():
    stream, logger = _capture()
    with bind_trace_id("f" * 32):
        logger.info("ask.received", extra={"fields": {"dept": "MA", "k": 20, "query_len": 12}})
    line = json.loads(stream.getvalue().strip())
    assert set(line) == {"ts", "level", "logger", "event", "trace_id", "fields"}
    assert (
        line["event"] == "ask.received"
        and line["trace_id"] == "f" * 32
        and line["fields"] == {"dept": "MA", "k": 20, "query_len": 12}
    )
    assert line["level"] == "INFO" and line["logger"] == "medops.test" and line["ts"].endswith("+00:00")


def test_trace_id_is_null_when_unbound_and_unicode_is_preserved():
    stream, logger = _capture()
    logger.warning("说明书 查询失败")
    line = json.loads(stream.getvalue().strip())
    assert line["trace_id"] is None and line["event"] == "说明书 查询失败"


def test_sensitive_keys_and_secret_substrings_are_redacted():
    stream, logger = _capture()
    fake_key = "sk-" + "ABCDEFGHIJKLMNOP"
    logger.info(
        f"login for user@example.com with Bearer abc.def-123 and key {fake_key}",
        extra={
            "fields": {
                "Authorization": "Bearer xyz",
                "password": "hunter2",
                "nested": {"api_key": "k", "ok": "keep"},
                "jwt": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMifQ.abcdefghijklmnop",
                "list": ["sk-QWERTYUIOPAS", "fine"],
            }
        },
    )
    line = json.loads(stream.getvalue().strip())
    text = json.dumps(line, ensure_ascii=False)
    for secret in (
        "user@example.com",
        "abc.def-123",
        fake_key,
        "Bearer xyz",
        "hunter2",
        "eyJhbGciOiJIUzI1NiJ9",
        "sk-QWERTYUIOPAS",
    ):
        assert secret not in text, secret
    assert line["fields"]["Authorization"] == REDACTED and line["fields"]["password"] == REDACTED
    assert line["fields"]["nested"] == {"api_key": REDACTED, "ok": "keep"} and line["fields"]["list"][1] == "fine"


def test_exception_is_serialized_and_redacted():
    stream, logger = _capture()
    try:
        raise RuntimeError("token leak sk-ZZZZZZZZZZZZ")
    except RuntimeError:
        logger.exception("worker.failed")
    line = json.loads(stream.getvalue().strip())
    assert (
        line["level"] == "ERROR" and "RuntimeError" in line["exception"] and "sk-ZZZZZZZZZZZZ" not in line["exception"]
    )


def test_configure_is_idempotent_and_respects_level():
    stream, logger = _capture("WARNING")
    configure_logging("WARNING", stream=stream)
    logger.info("hidden")
    logger.warning("shown")
    lines = [json.loads(x) for x in stream.getvalue().splitlines()]
    assert [x["event"] for x in lines] == ["shown"] and len(logging.getLogger().handlers) == 1


def test_redact_is_pure_for_non_sensitive_values():
    assert redact({"a": 1, "b": [1, "x"], "c": None}) == {"a": 1, "b": [1, "x"], "c": None}
    assert isinstance(JsonFormatter(), logging.Formatter)


class _Opaque:
    def __str__(self) -> str:
        return "Bearer sk-" + "SHOULDNOTLEAK123"


def test_bytes_and_unknown_objects_never_reach_str_serialization():
    stream, logger = _capture()
    logger.info(
        "payload",
        extra={"fields": {"raw": b"Bearer sk-BYTESLEAK12345", "obj": _Opaque(), "mv": memoryview(b"sk-MEMVIEWLEAK12")}},
    )
    text = stream.getvalue()
    assert "SHOULDNOTLEAK" not in text and "BYTESLEAK" not in text and "MEMVIEWLEAK" not in text
    line = json.loads(text.strip())
    assert line["fields"]["raw"].startswith("<bytes len=") and line["fields"]["obj"] == "<_Opaque>"


def test_cycles_depth_size_and_length_are_bounded():
    stream, logger = _capture()
    cyc: dict = {"name": "x"}
    cyc["self"] = cyc
    deep: dict = {}
    cur = deep
    for _ in range(30):
        cur["d"] = {}
        cur = cur["d"]
    logger.info(
        "bounded",
        extra={
            "fields": {"cyc": cyc, "deep": deep, "many": list(range(1000)), "long": "a" * 10_000 + "sk-TAILSECRET123"}
        },
    )
    line = json.loads(stream.getvalue().strip())
    f = line["fields"]
    assert f["cyc"]["self"] == "<cycle>"
    assert "<max-depth>" in json.dumps(f["deep"])
    assert len(f["many"]) == 201 and f["many"][-1].startswith("<truncated")
    assert len(f["long"]) < 2100 and "TAILSECRET" not in f["long"]


def test_format_failure_emits_safe_record_without_raw_content():
    stream, logger = _capture()
    logger.info("bad format %s %s sk-ARGSECRET1234", "only-one")  # getMessage() raises TypeError
    line = json.loads(stream.getvalue().strip())
    assert line["event"] == "<log-format-error>" and line["error"] == "TypeError"
    assert "ARGSECRET" not in stream.getvalue()


def test_secret_crossing_the_truncation_boundary_leaves_no_fragment():
    from medops.core.logging import MAX_STRING

    secret = "sk-" + "ABCDEFGHIJKLMNOPQRSTUV"
    text = "x" * (MAX_STRING - 5) + secret + "y" * 50
    out = redact(text)
    # the cut may land inside the "[REDACTED]" marker itself; what matters is that no key fragment survives
    assert isinstance(out, str) and "sk-" not in out and out.endswith("chars>")
    huge = "z" * 30_000 + secret
    assert redact(huge) == f"<string len={len(huge)} omitted>"


def test_container_processing_is_bounded_and_keys_are_never_stringified_beyond_limit():
    from collections.abc import Mapping as _Mapping

    from medops.core.logging import MAX_ITEMS

    class Bomb:
        def __str__(self) -> str:
            raise AssertionError("str() must not be called")

        __repr__ = __str__

    class LazyMap(_Mapping):
        def __init__(self, n: int) -> None:
            self.n, self.reads = n, 0

        def __getitem__(self, k):
            return k

        def __len__(self):
            return self.n

        def __iter__(self):
            for i in range(self.n):
                self.reads += 1
                yield (f"k{i}" if i < MAX_ITEMS else Bomb())

    m = LazyMap(600)
    out = redact(m)
    assert isinstance(out, dict) and m.reads <= MAX_ITEMS + 1 and out["<truncated>"] == "more keys omitted"
    assert redact({Bomb(): 1, 2: "two", ("t",): 3}) == {"<key:Bomb>": 1, "2": "two", "<key:tuple>": 3}
    out_set = redact({Bomb(), "a"})  # set members are values, never repr()'d for ordering
    assert isinstance(out_set, list) and "<Bomb>" in out_set and "a" in out_set
