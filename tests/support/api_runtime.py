"""Shared api runtime test support; no collected test cases."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from medops.api.app import create_app
from medops.application.audit import InMemoryTraceStore
from medops.application.policy_loader import ReleasedPolicySet, RequestPolicies
from medops.core.errors import ErrorCode, InfrastructureError
from medops.domain.common import Dept
from medops.domain.query import resolve_query_context
from medops.harness.dependencies import HarnessDeps
from medops.harness.executions import InMemoryExecutionStore
from medops.infrastructure.identity import Authenticator, JwtVerifier, Principal, StaticDirectory, pseudonym
from medops.infrastructure.llm.meter import MeteredGateway
from tests.support.harness import fast_specs
from tests.support.harness_data import versions
from tests.support.identity import AUDIENCE, ISSUER, PSEUDONYM_KEY, TestIssuer

ISSUER_OBJ = TestIssuer()


ANSWER = {"claims": [{"text": "6 至 12 歲孩童口服 100 mg，一天三次。", "citation_chunk_ids": ["c1"]}]}


QUERY = "拔痛酸錠用於6至12歲兒童時口服劑量如何給予？"


class FakeRuntime:
    observation_window = timedelta(hours=24)
    allow_drill = False

    def __init__(self, retrieval, gateway, *, fail_connection=False):
        self.authenticator = Authenticator(
            verifier=JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=ISSUER_OBJ.jwks), pseudonym_key=PSEUDONYM_KEY
        )
        self.versions = versions()
        self.retrieval, self.gateway, self.fail_connection = retrieval, gateway, fail_connection
        self.store = InMemoryExecutionStore()
        self.traces = InMemoryTraceStore()
        self.bound: list[Dept] = []
        self.readiness = True

    @contextmanager
    def connection(self):
        if self.fail_connection:
            raise InfrastructureError(ErrorCode.dependency_unavailable, detail="db down", retryable=True)
        yield "conn"

    def directory(self, conn):
        return StaticDirectory(
            {
                pseudonym("user-1", PSEUDONYM_KEY): Principal(
                    dept=Dept.MA, roles=("analyst",), scopes=frozenset({"MA:read"})
                )
            }
        )

    def bind_identity(self, conn, user):
        self.bound.append(user.dept)

    def route_policies(self, conn, user):
        return RequestPolicies(ReleasedPolicySet.empty(), self.versions)

    def build_deps(self, conn, user, request, routed=None, *, query_context=None):
        context = query_context or resolve_query_context(
            request.historical.model_dump() if request.historical else None
        )
        return HarnessDeps(
            retrieval=self.retrieval,
            gateway=MeteredGateway(self.gateway),
            answer_model_id="gpt-6-sol",
            specs=fast_specs(),
            sleep=lambda s: None,
            clock=lambda: datetime(2026, 9, 23, tzinfo=UTC),
            executions=self.store,
            as_of=context.as_of,
            query_context=context,
        )

    def trace_store(self, conn):
        return self.traces

    def payload_writer(self, conn):
        return None  # restricted payloads are off unless a test installs a writer (DEC-013)

    def validate_final_output(self, conn, user, evidence, context, *, authorization=None):
        # Explicit in-memory adapter: no PostgreSQL fact plane in these contract tests.
        from medops.infrastructure.db.final_output import require_same_user

        require_same_user(user, self.authenticator.authenticate(authorization, self.directory(conn)))

    def validate_privileged_access(self, identity_conn, target_conn, user, *, authorization, mutation=False):
        # Memory directory revalidation only; real fences are integration-tested.
        from medops.infrastructure.db.final_output import require_same_user

        require_same_user(user, self.authenticator.authenticate(authorization, self.directory(identity_conn)))

    def ready(self):
        return self.readiness

    def validate_task_result(self, conn, user, record, *, authorization=None):
        pass  # explicit in-memory adapter; PostgreSQL binding tested separately


def client(runtime) -> TestClient:
    return TestClient(create_app(runtime), raise_server_exceptions=False)


def auth() -> dict[str, str]:
    return {"Authorization": "Bearer " + ISSUER_OBJ.token()}
