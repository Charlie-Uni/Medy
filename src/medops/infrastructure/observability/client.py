"""Destination-bound HTTP transport for the pinned Langfuse score protocol."""

from __future__ import annotations

from typing import Any

import httpx

from medops.core.canonical import canonical_hash
from medops.core.config import check_langfuse_base_url
from medops.infrastructure.observability.errors import ScoreExportError
from medops.infrastructure.observability.schema import FORMAT, validate_score_event


class LangfuseScores:
    def __init__(
        self, base_url: str, public_key: str, secret_key: str, *, transport: httpx.BaseTransport | None = None
    ):
        check_langfuse_base_url(base_url)
        if not public_key or not secret_key:
            raise ValueError("score export needs both Langfuse API keys")
        self.base_url = base_url.rstrip("/")
        self.destination = canonical_hash({"base_url": self.base_url, "public_key": public_key, "format": FORMAT})
        self._client = httpx.Client(
            auth=(public_key, secret_key),
            timeout=10,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def _require_trace(self, trace_id: str) -> None:
        # Metadata only; this prevents orphan scores for old random OTel IDs or dropped/off telemetry.
        try:
            response = self._client.get(
                self.base_url + "/api/public/v2/observations",
                params={"traceId": trace_id, "fields": "core", "limit": 1},
            )
        except httpx.HTTPError:
            raise ScoreExportError("trace_lookup_transport_failure") from None
        if response.status_code != 200:
            raise ScoreExportError(f"trace_lookup_http_{response.status_code}")
        try:
            rows = response.json()["data"]
            if not isinstance(rows, list) or not rows or any(row.get("traceId") != trace_id for row in rows):
                raise ValueError("not visible")
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ScoreExportError("trace_not_visible") from None

    def send(self, event: dict[str, Any]) -> None:
        validate_score_event(event)
        self._require_trace(event["body"]["traceId"])
        # Pinned v4.54.0 compatibility path: score events remain supported in events-only mode.
        # POST /scores rebuilds the timestamp on each attempt; it cannot preserve cross-day dedup identity.
        try:
            response = self._client.post(self.base_url + "/api/public/ingestion", json={"batch": [event]})
        except httpx.HTTPError:
            raise ScoreExportError("transport_failure") from None
        if response.status_code not in {200, 207}:
            raise ScoreExportError(f"http_{response.status_code}")
        try:
            data = response.json()
            success = data.get("successes", [])
            accepted = {item["id"] for item in success}
            if (
                data.get("errors")
                or len(success) != 1
                or accepted != {event["id"]}
                or not 200 <= success[0].get("status", 200) < 300
            ):
                raise ValueError("not acknowledged")
        except (ValueError, TypeError, KeyError, AttributeError):
            raise ScoreExportError("event_not_acknowledged") from None
