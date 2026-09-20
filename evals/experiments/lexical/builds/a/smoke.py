"""Synthetic A pretokenization/FTS smoke in connection-local temporary tables.

This uses the existing PG16 development server and rolls back. It does not read
the probe, modify permanent tables, or claim ordinary-role/RLS adapter coverage.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

import jieba
import psycopg

from medops.core.config import Settings
from medops.retrieval.lexical.tokenizer import JiebaTokenizerV1


def main() -> int:
    tokenizer = JiebaTokenizerV1()
    config = Settings()
    secret = config.database_admin_url or config.database_url
    checks = []
    with psycopg.connect(secret.get_secret_value()) as conn:
        version = conn.execute("show server_version").fetchone()[0]
        conn.execute(
            "create temp table dec001_a_smoke (id text primary key, dept text, tokens tsvector) on commit drop"
        )
        rows = [
            ("a-1", "MA", "alpha 研究 PROT-2024-017 30 mg"),
            ("a-2", "PV", "alpha 研究 PROT-2024-017 30 mg"),
            ("a-3", "MA", "alpha 研究 PROT-2024-017 30 mg"),
            ("a-4", "MA", "beta 随访登记"),
        ]
        for cid, dept, content in rows:
            conn.execute(
                "insert into dec001_a_smoke values (%s,%s,to_tsvector('simple',%s))",
                (cid, dept, " ".join(tokenizer.tokenize(content))),
            )
        conn.execute("create index on dec001_a_smoke using gin(tokens)")
        cte = """with q as (
                   select string_agg(quote_literal(term), ' | ')::tsquery as query
                   from unnest(tsvector_to_array(to_tsvector('simple', %s))) as term
                 ), eligible as (
                   select id, ts_rank_cd(tokens,q.query,0) as score
                   from dec001_a_smoke cross join q where dept=%s and tokens @@ q.query
                 ) """
        sql = cte + """select id,score,(select count(*) from eligible) as eligible_count
                       from eligible order by score desc,id asc limit %s"""
        cases = [
            ("alpha", "MA", 1, ["a-1"], 2),
            ("研究", "MA", 20, ["a-1", "a-3"], 2),
            ("PROT-2024-017", "PV", 20, ["a-2"], 1),
            ("unmatched", "MA", 20, [], 0),
            ("!!!", "MA", 20, [], 0),
            ("alpha | beta", "MA", 20, ["a-1", "a-3", "a-4"], 3),
        ]
        for query, dept, k, expected, count in cases:
            words = " ".join(tokenizer.tokenize(query))
            first = conn.execute(sql, (words, dept, k)).fetchall()
            second = conn.execute(sql, (words, dept, k)).fetchall()
            assert first == second, "synthetic ranking must repeat exactly"
            ids = [row[0] for row in first]
            # Different matched terms may have different rank; equality order is asserted above for identical rows.
            actual_count = conn.execute(cte + "select count(*) from eligible", (words, dept)).fetchone()[0]
            assert set(ids) == set(expected) and actual_count == count
            assert all(row[2] == actual_count for row in first)
            if query == "alpha":
                assert ids == expected
            checks.append({"query": query, "dept": dept, "k": k, "ids": ids, "eligible_count": actual_count})
        conn.rollback()
    print(
        json.dumps(
            {
                "status": "synthetic_smoke_passed",
                "postgresql": version,
                "tokenizer": tokenizer.tokenizer_version,
                "jieba": importlib.metadata.version("jieba"),
                "dictionary_sha256": hashlib.sha256(
                    (Path(jieba.__file__).parent / "dict.txt").read_bytes()
                ).hexdigest(),
                "query_predicate": "OR of simple-FTS lexemes from identical application-pretokenized input",
                "ranking": "ts_rank_cd normalization=0, then id ASC",
                "checks": checks,
                "temporary_tables_rolled_back": True,
                "real_probe_used": False,
                "rls_verified": False,
                "production_adapter_implemented": False,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (psycopg.Error, ValueError, AssertionError) as exc:
        print(json.dumps({"status": "failed", "error_type": type(exc).__name__}))
        raise SystemExit(1) from None
