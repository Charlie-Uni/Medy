"""PUBLIC Agent audit HTTP environment using the real production identity/DB wiring."""

from uuid import uuid4

import psycopg

from medops.bootstrap.runtime import ProductionRuntime
from medops.core.config import Settings
from medops.infrastructure.identity import Authenticator, JwtVerifier, pseudonym
from medops.infrastructure.llm.fake import FakeModelGateway
from tests.support.api_runtime import ISSUER_OBJ
from tests.support.harness_data import versions
from tests.support.identity import AUDIENCE, ISSUER, PSEUDONYM_KEY


def audit_runtime(case, *, roles=("admin",)):
    sub = "PUBLIC-agent-audit-" + uuid4().hex
    pid = pseudonym(sub, PSEUDONYM_KEY)
    db = case["db"]
    with psycopg.connect(db["owner"]) as conn:
        conn.execute(
            "insert into principals(sub_pseudonym,dept,roles,scopes,created_by) values (%s,'MA',%s,array['MA:read'],'PUBLIC-agent-audit')",
            (pid, list(roles)),
        )
    runtime = ProductionRuntime(
        settings=Settings(_env_file=None, database_url=db["users"]["app"], redis_url="redis://localhost:6379/0"),
        authenticator=Authenticator(
            verifier=JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=ISSUER_OBJ.jwks),
            pseudonym_key=PSEUDONYM_KEY,
        ),
        gateway=FakeModelGateway(),
        embedding=None,
        reranker=None,
        versions=versions(),
        _dsn=db["users"]["app"],
        _restricted_dsn=db["users"]["restricted"],
        _key_provider=case["provider"],
    )
    headers = {"Authorization": "Bearer " + ISSUER_OBJ.token(sub)}
    return runtime, headers, pid
