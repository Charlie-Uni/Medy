"""Shared mcp runtime test support; no collected test cases."""

from __future__ import annotations

from contextlib import contextmanager

from medops.application.search import SearchExecution
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import Dept, DocStatus, DocType
from medops.infrastructure.identity import Authenticator, JwtVerifier, Principal, StaticDirectory, pseudonym
from medops.mcp.contracts import (
    ChunkView,
    DocumentVersionView,
    ListActiveVersionsOutput,
    SearchDocumentsOutput,
    VerifyCitationOutput,
)
from tests.support.harness_data import evidence
from tests.support.identity import AUDIENCE, ISSUER, PSEUDONYM_KEY, TestIssuer

ISSUER_OBJ = TestIssuer()


CHUNK = evidence(
    "11111111-1111-4111-8111-111111111111", "每日最高之建議劑量為 8mg。", doc_id="22222222-2222-4222-8222-222222222222"
)


class FakeService:
    def __init__(self, user):
        self.user = user
        self.audit_stats = SearchExecution(())

    def audit_snapshot(self):
        return {"synthetic": True}

    def search_documents(self, inp):
        self.audit_stats = SearchExecution(
            (),
            model_calls=1,
            tokens=17,
            cost_usd=0.002,
            retrieval_version="retrieval-canary",
            policy_version="policy-canary",
            cache_hit=False,
        )
        if inp.query == "fail-after-model":
            raise InfrastructureError(ErrorCode.dependency_unavailable, "retrieval failed")
        if inp.query == "uncaught-after-model":
            raise ValueError("synthetic-private-error-message")
        return SearchDocumentsOutput(hits=(), requested_k=inp.k, candidate_exhausted=True)

    def get_chunk(self, inp):
        if inp.chunk_id != CHUNK.citation.chunk_id:
            raise BusinessError(ErrorCode.not_found, "chunk not found")
        import hashlib

        return ChunkView(
            citation=CHUNK.citation,
            content=CHUNK.text,
            content_hash=hashlib.sha256(CHUNK.text.encode()).hexdigest(),
            status=DocStatus.active,
        )

    def verify_citation(self, inp):
        return VerifyCitationOutput(
            exists=inp.citation.chunk_id == CHUNK.citation.chunk_id,
            status=DocStatus.active if inp.citation.chunk_id == CHUNK.citation.chunk_id else None,
            fields_match=inp.citation == CHUNK.citation,
        )

    def list_active_versions(self, inp):
        view = DocumentVersionView(
            doc_id=CHUNK.citation.doc_id,
            family_id=inp.family_id,
            title="瑪爾胰仿單",
            doc_type=DocType.label,
            version="v1",
            effective_from=CHUNK.citation.effective_date,
        )
        return ListActiveVersionsOutput(family_id=inp.family_id, active=view)


class FakeRuntime:
    def __init__(self, *, with_auth: bool, dev_identity=None):
        self.authenticator = (
            Authenticator(
                verifier=JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=ISSUER_OBJ.jwks),
                pseudonym_key=PSEUDONYM_KEY,
            )
            if with_auth
            else None
        )
        self.dev_identity = dev_identity
        self.served: list[str] = []
        self.audited: list = []
        self.fail_audit = False
        self.payloads = []

    @contextmanager
    def directory(self):
        yield StaticDirectory(
            {pseudonym("user-1", PSEUDONYM_KEY): Principal(dept=Dept.MA, scopes=frozenset({"MA:read"}))}
        )

    @contextmanager
    def service(self, user):
        self.served.append(user.dept.value)
        yield FakeService(user)

    def audit(self, trace, *, payloads=None):
        if self.fail_audit:
            raise RuntimeError("audit store down")
        self.audited.append(trace)
        self.payloads.append(payloads)

    @contextmanager
    def final_output(self, user, service, inp, result, *, authorization=None):
        # Explicit in-memory service; production is covered by ordinary-role PG tests.
        yield
