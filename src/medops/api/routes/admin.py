"""Document governance and policy approval, release and rollback."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import APIRouter, Request
from pydantic import BaseModel

from medops.api.authorization import privileged_connection
from medops.api.headers import IDEMPOTENCY_KEY_HEADER
from medops.api.ports import ApiRuntime
from medops.application.admin import (
    DocumentAdminService,
    PolicyService,
    idempotent,
)
from medops.application.contracts import (
    DocumentAclRequest,
    DocumentAclResponse,
    DocumentDetail,
    DocumentListResponse,
    DocumentStatusRequest,
    PolicyDecisionRequest,
    PolicyListResponse,
    PolicyPromoteRequest,
    PolicyReleaseRequest,
    PolicyResponse,
    PolicyRollbackRequest,
)
from medops.domain.identity import UserContext

M = TypeVar("M", bound=BaseModel)


def build_router(runtime: ApiRuntime, *, idempotency_ttl_s: int) -> APIRouter:
    router = APIRouter()

    def _documents(conn: Any) -> DocumentAdminService:
        store, actions = runtime.document_admin(conn)
        return DocumentAdminService(store=store, actions=actions)

    def _idempotent(
        request: Request,
        conn: Any,
        user: UserContext,
        route: str,
        payload: BaseModel,
        model: type[M],
        produce: Callable[[], M],
    ) -> M:
        # Called within the privileged write transaction, so action and receipt commit together.
        return idempotent(
            runtime.receipt_store(conn),
            user,
            route,
            request.headers.get(IDEMPOTENCY_KEY_HEADER),
            payload,
            model,
            produce,
            ttl_s=idempotency_ttl_s,
        )

    @router.get("/admin/documents", response_model=DocumentListResponse)
    def list_documents(
        request: Request, dept: str | None = None, status: str | None = None, family_id: str | None = None
    ) -> DocumentListResponse:
        with privileged_connection(runtime, request, "admin") as (_, conn):
            return _documents(conn).list(dept=dept, status=status, family_id=family_id)

    @router.get("/admin/documents/{doc_id}", response_model=DocumentDetail)
    def get_document(doc_id: str, request: Request) -> DocumentDetail:
        with privileged_connection(runtime, request, "admin") as (_, conn):
            return _documents(conn).get(doc_id)

    @router.patch("/admin/documents/{doc_id}/status", response_model=DocumentDetail)
    def change_document_status(doc_id: str, body: DocumentStatusRequest, request: Request) -> DocumentDetail:
        with privileged_connection(runtime, request, "admin", mutation=True) as (admin, conn):
            service = _documents(conn)
            return _idempotent(
                request,
                conn,
                admin,
                f"PATCH /admin/documents/{doc_id}/status",
                body,
                DocumentDetail,
                lambda: service.change_status(admin, doc_id, body),
            )

    @router.patch("/admin/documents/{doc_id}/acl", response_model=DocumentAclResponse)
    def change_document_acl(doc_id: str, body: DocumentAclRequest, request: Request) -> DocumentAclResponse:
        with privileged_connection(runtime, request, "admin", mutation=True) as (admin, conn):
            service = _documents(conn)
            return _idempotent(
                request,
                conn,
                admin,
                f"PATCH /admin/documents/{doc_id}/acl",
                body,
                DocumentAclResponse,
                lambda: service.change_acl(admin, doc_id, body),
            )

    @router.get("/admin/policies/candidates", response_model=PolicyListResponse)
    def list_policy_candidates(request: Request) -> PolicyListResponse:
        with privileged_connection(runtime, request, "approver", "admin") as (_, conn):
            return _policy_service(conn).list_candidates()

    @router.get("/admin/policies/{policy_id}", response_model=PolicyResponse)
    def get_policy(policy_id: str, request: Request) -> PolicyResponse:
        with privileged_connection(runtime, request, "approver", "admin") as (_, conn):
            return _policy_service(conn).get(policy_id)

    @router.post("/admin/policies/{policy_id}/approve", response_model=PolicyResponse)
    def decide_policy(policy_id: str, body: PolicyDecisionRequest, request: Request) -> PolicyResponse:
        with privileged_connection(runtime, request, "approver", mutation=True) as (approver, conn):
            service = _policy_service(conn)
            return _idempotent(
                request,
                conn,
                approver,
                f"POST /admin/policies/{policy_id}/approve",
                body,
                PolicyResponse,
                lambda: service.decide(approver, policy_id, body),
            )

    def _policy_service(conn: Any) -> PolicyService:
        return PolicyService(
            store=runtime.policy_store(conn),
            observation_window=runtime.observation_window,
            allow_drill=runtime.allow_drill,
        )

    @router.post("/admin/policies/{policy_id}/release", response_model=PolicyResponse)
    def release_policy(policy_id: str, body: PolicyReleaseRequest, request: Request) -> PolicyResponse:
        with privileged_connection(runtime, request, "admin", mutation=True) as (admin, conn):
            service = _policy_service(conn)
            return _idempotent(
                request,
                conn,
                admin,
                f"POST /admin/policies/{policy_id}/release",
                body,
                PolicyResponse,
                lambda: service.release(admin, policy_id, body),
            )

    @router.post("/admin/policies/{policy_id}/promote", response_model=PolicyResponse)
    def promote_policy(policy_id: str, body: PolicyPromoteRequest, request: Request) -> PolicyResponse:
        with privileged_connection(runtime, request, "approver", mutation=True) as (approver, conn):
            service = _policy_service(conn)
            return _idempotent(
                request,
                conn,
                approver,
                f"POST /admin/policies/{policy_id}/promote",
                body,
                PolicyResponse,
                lambda: service.promote(approver, policy_id, body),
            )

    @router.post("/admin/policies/{policy_id}/rollback", response_model=PolicyResponse)
    def rollback_policy(policy_id: str, body: PolicyRollbackRequest, request: Request) -> PolicyResponse:
        with privileged_connection(runtime, request, "admin", mutation=True) as (admin, conn):
            service = _policy_service(conn)
            return _idempotent(
                request,
                conn,
                admin,
                f"POST /admin/policies/{policy_id}/rollback",
                body,
                PolicyResponse,
                lambda: service.rollback(admin, policy_id, body),
            )

    return router
