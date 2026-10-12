"""The shared helper retains local RLS identity and rollback on real PostgreSQL."""

import psycopg
import pytest

from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.evals.transactions import department_transaction, dept_connection
from medops.infrastructure.db.deadline import DeadlineConnection


@pytest.mark.parametrize("fail", [False, True])
def test_evaluation_departments_are_local_and_failed_work_rolls_back(login_users, fail):
    with psycopg.connect(login_users["app"]["dsn"]) as conn:
        before = conn.execute("select current_setting('medops.dept', true)").fetchone()[0] or ""
        conn.rollback()
        for dept in (Dept.PV, Dept.MA):
            user = UserContext(
                user_id="synthetic-eval", dept=dept, roles=("analyst",), acl_scopes=frozenset({f"{dept.value}:read"})
            )
            try:
                with dept_connection(conn, user) as scoped:
                    assert isinstance(scoped, DeadlineConnection) and scoped._conn is conn
                    assert scoped.execute("select current_setting('medops.dept', true)").fetchone()[0] == dept.value
                    if fail:
                        raise ValueError("synthetic eval failure")
            except ValueError:
                assert fail
            assert (conn.execute("select current_setting('medops.dept', true)").fetchone()[0] or "") == before
            conn.rollback()
        with department_transaction(conn, "CO") as raw:
            assert raw is conn
            assert raw.execute("select current_setting('medops.dept', true)").fetchone()[0] == "CO"
