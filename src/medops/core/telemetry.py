"""OpenTelemetry spans (M3-09 first slice; baseline 5.10). One tracer for the process; spans carry the MedOps
trace id, task id and version identifiers as attributes so API, worker and MCP spans of one request can be
joined. No span attribute ever holds evidence text, prompts or model output (INV-OBS-03). Without an OTLP
endpoint the tracer is a no-op; tests install an in-memory exporter through `set_tracer_provider`."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter
from opentelemetry.sdk.trace.id_generator import RandomIdGenerator
from opentelemetry.trace import Link, Status, StatusCode

from medops.core.tracing import bind_trace_id, current_trace_id, is_valid_trace_id

if TYPE_CHECKING:
    from medops.core.config import Settings

_provider: TracerProvider | None = None
ATTR_TRACE = "medops.trace_id"
ATTR_TASK = "medops.task_id"
ATTR_POLICY = "medops.policy_version"
ATTR_RETRIEVAL = "medops.retrieval_version"
_ALLOWED_VALUE_TYPES = (str, bool, int, float)
_metadata: ContextVar[dict[str, str] | None] = ContextVar("medops_telemetry_metadata", default=None)
_VERSION_FIELDS = ("policy_version", "retrieval_version", "model_config_version", "skill_version_set")


class BusinessTraceIdGenerator(RandomIdGenerator):
    """Root spans use the server-generated business ID; never accept incoming user trace headers."""

    def generate_trace_id(self) -> int:
        value = current_trace_id()
        if value and is_valid_trace_id(value) and int(value, 16):
            return int(value, 16)
        return super().generate_trace_id()


@contextmanager
def run_metadata(trace_id: str, versions: Mapping[str, Any], *, kind: str) -> Iterator[None]:
    """Propagate only version identifiers, within this process (no outbound OTel baggage)."""
    attrs = dict(_metadata.get() or {})
    attrs["langfuse.trace.name"] = f"medops.{kind}"
    for key in _VERSION_FIELDS:
        value = versions.get(key)
        if value is None:
            continue
        rendered = ",".join(value) if key == "skill_version_set" else str(value)
        attrs[f"medops.{key}"] = rendered
        attrs[f"langfuse.trace.metadata.{key}"] = rendered
    token = _metadata.set(attrs)
    try:
        with bind_trace_id(trace_id):
            current = trace.get_current_span()
            # Update the HTTP/worker parent with the actual routed versions, not startup defaults.
            if current.get_span_context().trace_id == int(trace_id, 16):
                annotate(current, **attrs)
            yield
    finally:
        _metadata.reset(token)


def set_tracer_provider(provider: TracerProvider | None) -> None:
    global _provider
    _provider = provider


def install_exporter(
    exporter: SpanExporter, *, service_name: str = "medops-copilot", batch: bool = True
) -> TracerProvider:
    provider = TracerProvider(
        resource=Resource.create({"service.name": service_name}), id_generator=BusinessTraceIdGenerator()
    )
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


def telemetry_options(settings: Settings) -> dict[str, Any]:
    """Use one explicit project for spans and scores; secrets never appear in log/config dumps."""
    endpoint = settings.otel_exporter_otlp_endpoint
    headers = settings.otel_exporter_otlp_headers.get_secret_value() if settings.otel_exporter_otlp_headers else None
    if settings.langfuse_base_url:
        import base64

        assert settings.langfuse_public_key is not None and settings.langfuse_secret_key is not None
        pair = settings.langfuse_public_key.get_secret_value() + ":" + settings.langfuse_secret_key.get_secret_value()
        auth = base64.b64encode(pair.encode()).decode("ascii")
        endpoint = settings.langfuse_base_url.rstrip("/") + "/api/public/otel"
        headers = "Authorization=Basic " + auth + ",x-langfuse-ingestion-version=4"
    return {"endpoint": endpoint, "headers": headers, "service_name": settings.otel_service_name}


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
    trace_id = current_trace_id()
    parent = trace.get_current_span().get_span_context()
    separate = bool(trace_id and int(trace_id, 16) and parent.is_valid and parent.trace_id != int(trace_id, 16))
    # A replay may have a fresh business trace inside an HTTP request. Link it, rather than assigning
    # the HTTP trace's ID to the replay. Exception messages/stack traces can contain medical content.
    with tracer.start_as_current_span(
        name,
        context=otel_context.Context() if separate else None,
        links=[Link(parent)] if separate else None,
        record_exception=False,
        set_status_on_exception=False,
    ) as current:
        if trace_id:
            current.set_attribute(ATTR_TRACE, trace_id)
            current.set_attribute("langfuse.trace.metadata.medops_trace_id", trace_id)
        current.set_attribute("langfuse.observation.type", _observation_type(name))
        for key, value in _clean({**(_metadata.get() or {}), **attrs}).items():
            current.set_attribute(key, value)
        try:
            yield current
        except BaseException as exc:
            current.set_status(Status(StatusCode.ERROR, type(exc).__name__))
            current.set_attribute("error.type", type(exc).__name__)
            current.set_attribute("langfuse.observation.level", "ERROR")
            raise


def _observation_type(name: str) -> str:
    if name == "llm.call":
        return "generation"
    if name.startswith("retrieval.") and name != "retrieval.translate":
        return "retriever"
    if name in {"harness.run", "harness.node"}:
        return "chain"
    if name in {"skill.run", "worker.task", "mcp.tool"}:
        return "tool"
    return "span"


def annotate(current: trace.Span, **attrs: Any) -> None:
    for key, value in _clean(attrs).items():
        current.set_attribute(key, value)
    if attrs.get("error_code"):
        current.set_status(Status(StatusCode.ERROR, str(attrs["error_code"])))
        current.set_attribute("langfuse.observation.level", "ERROR")
