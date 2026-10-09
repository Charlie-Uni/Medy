"""`GET /metrics` (M3-10 first slice): Prometheus text with low-cardinality labels only, readable by ops/admin
principals, computed by the runtime's metrics source."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.api.auth import Principal, StaticDirectory, pseudonym
from medops.application.metrics import MetricsSnapshot, render_prometheus
from medops.domain.common import Dept
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.unit.api._auth_fixtures import PSEUDONYM_KEY
from tests.unit.api.test_ask_route import ISSUER_OBJ, FakeRuntime
from tests.unit.harness.test_run_ask import FakeRetrieval

SNAP = MetricsSnapshot(
    window_minutes=60,
    requests={("ask", "answered"): 12, ("ask", "escalated"): 3, ("task", "completed"): 2},
    escalations={"insufficient_evidence": 2, "high_risk_medical": 1},
    open_escalations=3,
    duration_ms_quantiles={("ask", "0.5"): 6200.0, ("ask", "0.95"): 12890.4},
    model_calls=30,
    tokens=45000,
    cost_usd_window=0.4123,
    cost_usd_month=8.75,
    tasks_by_status={"queued": 1, "completed": 4},
    oldest_queued_age_s=42.0,
    generated_at=datetime(2026, 9, 24, tzinfo=UTC),
)


class FakeSource:
    def snapshot(self, *, window_minutes, now):
        return SNAP


class MetricsRuntime(FakeRuntime):
    def __init__(self, roles=("ops",)):
        super().__init__(FakeRetrieval(), FakeModelGateway())
        self.roles = roles
        self.monthly_cap_usd = 30.0

    def directory(self, conn):
        return StaticDirectory(
            {
                pseudonym("user-1", PSEUDONYM_KEY): Principal(
                    dept=Dept.MA, roles=self.roles, scopes=frozenset({"MA:read"})
                )
            }
        )

    def metrics_source(self, conn):
        return FakeSource()


def test_render_is_prometheus_text_without_high_cardinality_labels():
    text = render_prometheus(SNAP, monthly_cap_usd=30.0)
    assert "# TYPE medops_requests_window gauge" in text
    assert 'medops_requests_window{kind="ask",outcome="answered"} 12' in text
    assert 'medops_escalations_window{reason_code="high_risk_medical"} 1' in text
    assert 'medops_request_duration_ms{kind="ask",quantile="0.95"} 12890.4' in text
    assert "medops_model_cost_usd_month 8.75" in text and "medops_model_budget_usd_cap 30.0" in text
    assert 'medops_tasks{status="queued"} 1' in text and "medops_task_queue_oldest_age_seconds 42.0" in text
    assert "trace_id" not in text and "user" not in text and "principal" not in text


def test_metrics_route_requires_ops_or_admin_role():
    ok = TestClient(create_app(MetricsRuntime(("ops",))), raise_server_exceptions=False)
    r = ok.get("/metrics", headers={"Authorization": "Bearer " + ISSUER_OBJ.token()})
    assert (
        r.status_code == 200
        and r.headers["content-type"].startswith("text/plain")
        and "medops_requests_window" in r.text
    )
    analyst = TestClient(create_app(MetricsRuntime(("analyst",))), raise_server_exceptions=False)
    assert analyst.get("/metrics", headers={"Authorization": "Bearer " + ISSUER_OBJ.token()}).status_code == 403
    assert ok.get("/metrics").status_code == 401


def test_index_metrics_report_counts_and_backlog_without_database_identifiers_or_metadata():
    health = {
        "ready": False,
        "database": "private-name",
        "database_identity": "private-fingerprint",
        "coverage": {"missing_embedding": 12, "active_documents_without_chunks": 1},
        "outbox": {
            "lexical-index": {"pending": 3, "oldest_age_s": 61.2},
            "retrieval-cache": {"pending": 4, "oldest_age_s": 62.3},
        },
        "problems": ["embedding_coverage_gap"],
    }
    text = render_prometheus(replace(SNAP, retrieval_integrity=health))
    assert "medops_retrieval_indexes_ready 0" in text
    assert "medops_index_missing_embedding 12" in text
    assert 'medops_outbox_pending{consumer="lexical-index"} 3' in text
    assert 'medops_outbox_oldest_age_seconds{consumer="retrieval-cache"} 62.3' in text
    assert 'medops_outbox_dead_lettered{consumer="lexical-index"} 0' in text
    assert "private" not in text and "embedding_coverage_gap" not in text
    unavailable = render_prometheus(replace(SNAP, retrieval_integrity={"ready": False}))
    assert "medops_retrieval_indexes_ready 0" in unavailable
    assert "medops_index_missing_embedding" not in unavailable  # unknown is not silently reported as zero
