"""Document governance and policy approval, release and rollback."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from fastapi import APIRouter, Request

from medops.api.contracts import (
    IDEMPOTENCY_KEY_HEADER,
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
from medops.api.ports import ApiRuntime
from medops.application.admin import (
    DocumentAdminService,
    PolicyService,
    idempotent,
)
from medops.application.metrics import has_role
from medops.core.errors import BusinessError, ErrorCode
from medops.domain.identity import UserContext


def build_router(runtime: ApiRuntime, *, idempotency_ttl_s: int) -> APIRouter:
    router = APIRouter()

    def _admin_user(request: Request, *roles: str) -> UserContext:
        with runtime.connection() as conn:
            user = runtime.authenticator.authenticate(request.headers.get("authorization"), runtime.directory(conn))
        if not has_role(user.roles, *roles):
            raise BusinessError(ErrorCode.forbidden, f"requires one of the roles: {', '.join(roles)}")
        return user

    def _documents(conn: Any) -> DocumentAdminService:
        store, actions = runtime.document_admin(conn)
        return DocumentAdminService(store=store, actions=actions)

    @router.get("/admin/documents", response_model=DocumentListResponse)
    def list_documents(
        request: Request, dept: str | None = None, status: str | None = None, family_id: str | None = None
    ) -> DocumentListResponse:
        _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            return _documents(conn).list(dept=dept, status=status, family_id=family_id)

    @router.get("/admin/documents/{doc_id}", response_model=DocumentDetail)
    def get_document(doc_id: str, request: Request) -> DocumentDetail:
        _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            return _documents(conn).get(doc_id)

    @router.patch("/admin/documents/{doc_id}/status", response_model=DocumentDetail)
    def change_document_status(doc_id: str, body: DocumentStatusRequest, request: Request) -> DocumentDetail:
        admin = _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            service = _documents(conn)
            return idempotent(
                runtime.receipt_store(conn),
                admin,
                f"PATCH /admin/documents/{doc_id}/status",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                DocumentDetail,
                lambda: service.change_status(admin, doc_id, body),
                ttl_s=idempotency_ttl_s,
            )

    @router.patch("/admin/documents/{doc_id}/acl", response_model=DocumentAclResponse)
    def change_document_acl(doc_id: str, body: DocumentAclRequest, request: Request) -> DocumentAclResponse:
        admin = _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            service = _documents(conn)
            return idempotent(
                runtime.receipt_store(conn),
                admin,
                f"PATCH /admin/documents/{doc_id}/acl",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                DocumentAclResponse,
                lambda: service.change_acl(admin, doc_id, body),
                ttl_s=idempotency_ttl_s,
            )

    @router.get("/admin/policies/candidates", response_model=PolicyListResponse)
    def list_policy_candidates(request: Request) -> PolicyListResponse:
        _admin_user(request, "approver", "admin")
        with runtime.admin_connection() as conn:
            return _policy_service(conn).list_candidates()

    @router.get("/admin/policies/{policy_id}", response_model=PolicyResponse)
    def get_policy(policy_id: str, request: Request) -> PolicyResponse:
        _admin_user(request, "approver", "admin")
        with runtime.admin_connection() as conn:
            return _policy_service(conn).get(policy_id)

    @router.post("/admin/policies/{policy_id}/approve", response_model=PolicyResponse)
    def decide_policy(policy_id: str, body: PolicyDecisionRequest, request: Request) -> PolicyResponse:
        approver = _admin_user(request, "approver")
        with runtime.admin_connection() as conn:
            service = _policy_service(conn)
            return idempotent(
                runtime.receipt_store(conn),
                approver,
                f"POST /admin/policies/{policy_id}/approve",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                PolicyResponse,
                lambda: service.decide(approver, policy_id, body),
                ttl_s=idempotency_ttl_s,
            )

    def _policy_service(conn: Any) -> PolicyService:
        return PolicyService(
            store=runtime.policy_store(conn),
            observation_window=getattr(runtime, "observation_window", timedelta(hours=24)),
            allow_drill=bool(getattr(runtime, "allow_drill", False)),
        )

    @router.post("/admin/policies/{policy_id}/release", response_model=PolicyResponse)
    def release_policy(policy_id: str, body: PolicyReleaseRequest, request: Request) -> PolicyResponse:
        admin = _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            service = _policy_service(conn)
            return idempotent(
                runtime.receipt_store(conn),
                admin,
                f"POST /admin/policies/{policy_id}/release",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                PolicyResponse,
                lambda: service.release(admin, policy_id, body),
                ttl_s=idempotency_ttl_s,
            )

    @router.post("/admin/policies/{policy_id}/promote", response_model=PolicyResponse)
    def promote_policy(policy_id: str, body: PolicyPromoteRequest, request: Request) -> PolicyResponse:
        approver = _admin_user(request, "approver")
        with runtime.admin_connection() as conn:
            service = _policy_service(conn)
            return idempotent(
                runtime.receipt_store(conn),
                approver,
                f"POST /admin/policies/{policy_id}/promote",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                PolicyResponse,
                lambda: service.promote(approver, policy_id, body),
                ttl_s=idempotency_ttl_s,
            )

    @router.post("/admin/policies/{policy_id}/rollback", response_model=PolicyResponse)
    def rollback_policy(policy_id: str, body: PolicyRollbackRequest, request: Request) -> PolicyResponse:
        admin = _admin_user(request, "admin")
        with runtime.admin_connection() as conn:
            service = _policy_service(conn)
            return idempotent(
                runtime.receipt_store(conn),
                admin,
                f"POST /admin/policies/{policy_id}/rollback",
                request.headers.get(IDEMPOTENCY_KEY_HEADER),
                body,
                PolicyResponse,
                lambda: service.rollback(admin, policy_id, body),
                ttl_s=idempotency_ttl_s,
            )

    return router
