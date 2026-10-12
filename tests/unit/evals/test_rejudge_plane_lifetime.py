"""Rejudging opens one read-only plane per database and closes it on success/failure."""

import json
from types import SimpleNamespace

import pytest

from medops.evals import fact_lookups
from medops.evals.tools.harness import safety_run


@pytest.mark.parametrize("fail", [False, True])
def test_rejudge_reuses_plane_and_closes_connections_when_a_judge_fails(tmp_path, monkeypatch, fail):
    samples = [{"sample_id": f"ss-{n}", "query": "synthetic", "expected": {}, "slices": []} for n in range(3)]
    rows = [
        {"sample_id": s["sample_id"], "query": s["query"], "database": "synthetic-plane", "claims": [], "detail": ""}
        for s in samples
    ]
    (tmp_path / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    opened, closed, seen = [], [], []

    def connect(dsn):
        conn = SimpleNamespace(read_only=False, close=lambda: closed.append(dsn))
        opened.append(conn)
        return conn

    def judge(sample, observations, plane):
        assert plane.admin.read_only and not closed
        seen.append(plane)
        if fail and len(seen) == 2:
            raise ValueError("synthetic judge failure")
        return [{"ok": True, "check": "fixture"}]

    monkeypatch.setattr(fact_lookups, "admin_dsn", lambda name: name)
    monkeypatch.setattr(fact_lookups.psycopg, "connect", connect)
    monkeypatch.setattr(safety_run, "load_drafts", lambda **kwargs: samples)
    monkeypatch.setattr(safety_run, "judge", judge)
    monkeypatch.setattr(safety_run, "summarize", lambda rows, *args: {"n": len(rows)})
    monkeypatch.setattr(safety_run, "report_markdown", lambda *args: "synthetic report")
    if fail:
        with pytest.raises(ValueError, match="synthetic judge failure"):
            safety_run.rejudge(tmp_path)
    else:
        assert safety_run.rejudge(tmp_path) == 0
    assert len(opened) == 1 and closed == ["synthetic-plane"]
    assert all(plane is seen[0] for plane in seen)
