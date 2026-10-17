"""Temporary PG control context; PUBLIC synthetic narrative, real pseudonym and DB clock."""

from datetime import timedelta
from uuid import uuid4

import psycopg

from medops.domain.identity import UserContext
from medops.infrastructure.db.agent_facts import bind_fact_database
from tests.support.pv_agent import run


def control_data(db):
    current = run()
    user = UserContext(user_id=uuid4().hex * 2, dept="PV", acl_scopes=frozenset({"PV:read"}))
    with psycopg.connect(db["owner"]) as conn:
        conn.execute(
            "insert into principals(sub_pseudonym,dept,roles,scopes,created_by) values (%s,'PV',array[]::text[],array['PV:read'],'agent-control-test')",
            (user.user_id,),
        )
        now = conn.execute("select clock_timestamp()").fetchone()[0]
        binding = bind_fact_database(conn)
        fact_id = binding.fact_database_id
    context = current.context.model_copy(
        update={
            "identity": current.context.identity.model_copy(
                update={"case_id": uuid4(), "task_id": uuid4(), "run_id": uuid4(), "attempt_id": uuid4()}
            ),
            "principal": user,
            "versions": current.context.versions.model_copy(update={"fact_database_id": fact_id}),
        }
    )
    current = current.model_copy(
        update={
            "context": context,
            "started_at": now - timedelta(seconds=1),
            "expires_at": now + timedelta(seconds=124),
        }
    )
    return db, current, binding
