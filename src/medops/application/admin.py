"""Admin services (M3-03 / DEC-012, record 74): document status and ACL management on published documents, and the
policy candidate lifecycle (four-eyes decision, gated release with a small canary, atomic rollback). Role checks
happen in the API layer; the services enforce the state machines and record who did what."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, TypeVar

from pydantic import BaseModel

from medops.api.contracts import (
    DocumentAclRequest,
    DocumentAclResponse,
    DocumentDetail,
    DocumentListResponse,
    DocumentStatusAction,
    DocumentStatusRequest,
    DocumentSummary,
    PolicyDecision,
    PolicyDecisionRequest,
    PolicyListResponse,
    PolicyReleaseRequest,
    PolicyResponse,
    PolicyRollbackRequest,
    PolicyStatus,
)
from medops.application.policy_loader import SUPPORTED_RELEASE_TARGETS
from medops.core.canonical import canonical_hash
from medops.core.errors import BusinessError, ErrorCode
from medops.domain.identity import UserContext

# ----------------------------------------------------------------------------------------------- idempotency

M = TypeVar("M", bound=BaseModel)


class ReceiptStore(Protocol):
    def find(self, principal: str, route: str, key: str) -> tuple[str, Mapping[str, Any]] | None: ...

    def put(
        self, principal: str, route: str, key: str, request_hash: str, receipt: Mapping[str, Any], expires_at: datetime
    ) -> None: ...


def idempotent(
    receipts: ReceiptStore | None,
    user: UserContext,
    route: str,
    key: str | None,
    payload: BaseModel,
    model: type[M],
    produce: Callable[[], M],
    *,
    ttl_s: int,
) -> M:
    """Same principal + route + key + payload -> the stored receipt; different payload -> 422 (baseline 3.2)."""
    if key is None or receipts is None:
        return produce()
    if not 1 <= len(key) <= 255:
        raise BusinessError(ErrorCode.invalid_request, "Idempotency-Key must be 1-255 characters")
    request_hash = canonical_hash(payload.model_dump(mode="json"))
    existing = receipts.find(user.user_id, route, key)
    if existing is not None:
        stored_hash, stored = existing
        if stored_hash != request_hash:
            raise BusinessError(ErrorCode.idempotency_payload_mismatch, "same Idempotency-Key with a different payload")
        return model.model_validate(stored)
    result = produce()
    receipts.put(
        user.user_id,
        route,
        key,
        request_hash,
        result.model_dump(mode="json"),
        datetime.now(UTC) + timedelta(seconds=ttl_s),
    )
    return result


# ----------------------------------------------------------------------------------------------- documents


class DocumentAdminStore(Protocol):
    def list(
        self, *, dept: str | None = None, status: str | None = None, family_id: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]: ...

    def get(self, doc_id: str) -> dict[str, Any] | None: ...

    def document_key(self, doc_id: str) -> str | None: ...


class DocumentActions(Protocol):
    """The publish-chain operations (ingestion.activate / ingestion.acl) bound to the admin connection."""

    def activate(self, document_key: str, effective_from: Any, *, actor: str, reason: str) -> None: ...

    def archive(self, document_key: str, effective_to: Any, *, actor: str, reason: str) -> None: ...

    def withdraw(self, document_key: str, *, actor: str, reason: str) -> None: ...

    def change_acl(
        self, document_key: str, *, grant: Sequence[str], revoke: Sequence[str], actor: str, reason: str
    ) -> Mapping[str, Any]: ...


def _project(model: type[M], row: Mapping[str, Any]) -> M:
    """Store rows carry every admin column; each contract model takes only its own fields (extra is forbidden)."""
    return model.model_validate({k: v for k, v in row.items() if k in model.model_fields})


def _refused(exc: Exception) -> BusinessError:
    text = str(exc)
    if "unknown document_key" in text:
        return BusinessError(ErrorCode.not_found, "document not found")
    return BusinessError(ErrorCode.status_conflict, text)


@dataclass
class DocumentAdminService:
    store: DocumentAdminStore
    actions: DocumentActions

    def list(self, *, dept: str | None, status: str | None, family_id: str | None) -> DocumentListResponse:
        items = tuple(
            _project(DocumentSummary, r) for r in self.store.list(dept=dept, status=status, family_id=family_id)
        )
        return DocumentListResponse(items=items, count=len(items))

    def get(self, doc_id: str) -> DocumentDetail:
        row = self.store.get(doc_id)
        if row is None:
            raise BusinessError(ErrorCode.not_found, "document not found")
        return _project(DocumentDetail, row)

    def change_status(self, user: UserContext, doc_id: str, request: DocumentStatusRequest) -> DocumentDetail:
        key = self.store.document_key(doc_id)
        if key is None:
            raise BusinessError(ErrorCode.not_found, "document not found")
        try:
            if request.action is DocumentStatusAction.activate:
                self.actions.activate(key, request.effective_date, actor=user.user_id, reason=request.reason)
            elif request.action is DocumentStatusAction.archive:
                self.actions.archive(key, request.effective_date, actor=user.user_id, reason=request.reason)
            else:
                self.actions.withdraw(key, actor=user.user_id, reason=request.reason)
        except ValueError as exc:  # ActivationRefused / AclChangeRefused are ValueErrors; nothing was changed
            raise _refused(exc) from None
        return self.get(doc_id)

    def change_acl(self, user: UserContext, doc_id: str, request: DocumentAclRequest) -> DocumentAclResponse:
        key = self.store.document_key(doc_id)
        if key is None:
            raise BusinessError(ErrorCode.not_found, "document not found")
        try:
            change = self.actions.change_acl(
                key,
                grant=[d.value for d in request.grant],
                revoke=[d.value for d in request.revoke],
                actor=user.user_id,
                reason=request.reason,
            )
        except ValueError as exc:
            raise _refused(exc) from None
        return DocumentAclResponse.model_validate({"doc_id": doc_id, "document_key": key, **change})


# ----------------------------------------------------------------------------------------------- policies


class PolicyStore(Protocol):
    def list(self, *, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]: ...

    def get(self, policy_id: str) -> dict[str, Any] | None: ...

    def decide(self, policy_id: str, *, status: str, decided_by: str, reason: str, at: datetime) -> bool: ...

    def release(
        self, policy_id: str, *, kind: str, name: str, canary_percent: int, actor: str, reason: str
    ) -> str | None: ...

    def rollback(self, policy_id: str, *, kind: str, name: str, actor: str, reason: str) -> str | None: ...


def gate_passed(evidence: Mapping[str, Any]) -> bool:
    """M3 stub of the M4-08 gate: the candidate must carry a gate report that passed. M4 computes the report
    (+5pp target, non-target drop <= 1pp, safety not below, worst of three runs)."""
    gate = evidence.get("gate")
    return isinstance(gate, Mapping) and gate.get("passed") is True


@dataclass
class PolicyService:
    store: PolicyStore
    clock: Callable[[], datetime] = lambda: datetime.now(UTC)

    def list_candidates(self) -> PolicyListResponse:
        items = tuple(PolicyResponse.model_validate(r) for r in self.store.list(status=PolicyStatus.candidate.value))
        return PolicyListResponse(items=items, count=len(items))

    def get(self, policy_id: str) -> PolicyResponse:
        row = self.store.get(policy_id)
        if row is None:
            raise BusinessError(ErrorCode.not_found, "policy not found")
        return PolicyResponse.model_validate(row)

    def decide(self, user: UserContext, policy_id: str, request: PolicyDecisionRequest) -> PolicyResponse:
        current = self.get(policy_id)
        if current.status is not PolicyStatus.candidate:
            raise BusinessError(
                ErrorCode.status_conflict, f"policy is {current.status.value}, only candidates can be decided"
            )
        if current.created_by == user.user_id:
            raise BusinessError(ErrorCode.forbidden, "four-eyes: the candidate's author cannot decide it")
        status = PolicyStatus.approved if request.decision is PolicyDecision.approve else PolicyStatus.rejected
        if not self.store.decide(
            policy_id, status=status.value, decided_by=user.user_id, reason=request.reason, at=self.clock()
        ):
            raise BusinessError(ErrorCode.status_conflict, "policy changed concurrently")
        return self.get(policy_id)

    def release(self, user: UserContext, policy_id: str, request: PolicyReleaseRequest) -> PolicyResponse:
        current = self.get(policy_id)
        if current.status is not PolicyStatus.approved:
            raise BusinessError(
                ErrorCode.status_conflict, f"policy is {current.status.value}, only approved policies can be released"
            )
        if not gate_passed(current.evidence):
            raise BusinessError(ErrorCode.gate_not_passed, "release requires a passing gate report in evidence.gate")
        if (current.kind.value, current.name) not in SUPPORTED_RELEASE_TARGETS:
            raise BusinessError(
                ErrorCode.policy_target_unsupported,
                f"the runtime cannot apply {current.kind.value}/{current.name}; releasable targets: "
                + ", ".join(sorted(f"{k}/{n}" for k, n in SUPPORTED_RELEASE_TARGETS)),
            )
        self.store.release(
            policy_id,
            kind=current.kind.value,
            name=current.name,
            canary_percent=request.canary_percent,
            actor=user.user_id,
            reason=request.reason,
        )
        return self.get(policy_id)

    def rollback(self, user: UserContext, policy_id: str, request: PolicyRollbackRequest) -> PolicyResponse:
        current = self.get(policy_id)
        if current.status is not PolicyStatus.released or not current.released:
            raise BusinessError(ErrorCode.status_conflict, "only the currently released policy can be rolled back")
        self.store.rollback(
            policy_id, kind=current.kind.value, name=current.name, actor=user.user_id, reason=request.reason
        )
        return self.get(policy_id)
