"""OpenTelemetry spans (M3-09 first slice; baseline 5.10). One tracer for the process; spans carry the MedOps
trace id, task id and version identifiers as attributes so API, worker and MCP spans of one request can be
joined. No span attribute ever holds evidence text, prompts or model output (INV-OBS-03). Without an OTLP
endpoint the tracer is a no-op; tests install an in-memory exporter through `set_tracer_provider`."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter
from opentelemetry.trace import Status, StatusCode

from medops.core.tracing import current_trace_id

_provider: TracerProvider | None = None
ATTR_TRACE = "medops.trace_id"
ATTR_TASK = "medops.task_id"
ATTR_POLICY = "medops.policy_version"
ATTR_RETRIEVAL = "medops.retrieval_version"
_ALLOWED_VALUE_TYPES = (str, bool, int, float)


def set_tracer_provider(provider: TracerProvider | None) -> None:
    global _provider
    _provider = provider


def install_exporter(
    exporter: SpanExporter, *, service_name: str = "medops-copilot", batch: bool = True
) -> TracerProvider:
    provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
    provider.add_span_processor(BatchSpanProcessor(exporter) if batch else SimpleSpanProcessor(exporter))
    set_tracer_provider(provider)
    return provider


def parse_headers(raw: str | None) -> dict[str, str]:
    """`Key=Value,Key2=Value2` -> headers. A value may itself contain `=` (base64); a malformed pair is an error."""
    headers: dict[str, str] = {}
    for pair in (raw or "").split(","):
        if not pair.strip():
            continue
        key, sep, value = pair.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise ValueError("OTLP headers must be Key=Value pairs separated by commas")
        headers[key.strip()] = value.strip()
    return headers


def configure_telemetry(
    *, endpoint: str | None, service_name: str = "medops-copilot", headers: str | None = None
) -> TracerProvider | None:
    """OTLP/HTTP exporter when an endpoint is configured; otherwise spans are not recorded. `headers` carries what
    the backend needs to accept the export (a collector needs none; Langfuse wants Basic auth)."""
    if not endpoint:
        set_tracer_provider(None)
        return None
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    exporter = OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces", headers=parse_headers(headers) or None)
    return install_exporter(exporter, service_name=service_name)


def shutdown() -> None:
    if _provider is not None:
        _provider.shutdown()


def flush(timeout_ms: int = 10_000) -> None:
    """Export whatever the batch processor still holds. Called from the API's lifespan shutdown because uvicorn
    re-raises the captured SIGTERM after a graceful stop (record 67): the process then dies by signal, `atexit`
    never runs and the spans of the last few seconds would be lost (record 77)."""
    if _provider is not None:
        _provider.force_flush(timeout_ms)


def _tracer() -> trace.Tracer:
    if _provider is None:
        return trace.NoOpTracer()
    return _provider.get_tracer("medops")


def _clean(attrs: Mapping[str, Any]) -> dict[str, str | bool | int | float]:
    out: dict[str, str | bool | int | float] = {}
    for key, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, _ALLOWED_VALUE_TYPES):
            out[key] = value
        else:
            out[key] = str(value)[:200]
    return out


@contextmanager
def span(name: str, **attrs: Any) -> Iterator[trace.Span]:
    """A span with the MedOps trace id attached; exceptions mark the span as error and propagate."""
    tracer = _tracer()
    with tracer.start_as_current_span(name) as current:
        trace_id = current_trace_id()
        if trace_id:
            current.set_attribute(ATTR_TRACE, trace_id)
        for key, value in _clean(attrs).items():
            current.set_attribute(key, value)
        try:
            yield current
        except BaseException as exc:
            current.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            current.set_attribute("error.type", type(exc).__name__)
            raise


def annotate(current: trace.Span, **attrs: Any) -> None:
    for key, value in _clean(attrs).items():
        current.set_attribute(key, value)
