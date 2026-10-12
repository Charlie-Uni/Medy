"""Final identity and full fact snapshots, fenced until the caller commits audit/result.

The fence is shared by readers and exclusive for ordinary fact writes (migration
0026). It is acquired after inference, never across provider calls. Reading again
without this fence leaves a check-to-commit race. No elevated connection is used.
"""

from collections.abc import Sequence
from typing import Any

from psycopg.pq import TransactionStatus

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.evidence import Evidence
from medops.domain.identity import UserContext
from medops.domain.query import QueryContext
from medops.infrastructure.identity import PgDirectory
from medops.retrieval.recheck import recheck_candidates, require_acl_enforced


def acquire_output_fence(conn: Any) -> None:
    if conn.autocommit or conn.info.transaction_status != TransactionStatus.INTRANS:
        raise InfrastructureError(
            ErrorCode.internal_error, detail="final output requires a caller-owned transaction", retryable=False
        )
    require_acl_enforced(conn)
    # A fixed short lock wait, in addition to the connection/active execution deadline.
    # The boundary's savepoint contains lock timeout failures so its audit remains usable.
    conn.execute("select set_config('lock_timeout','1000ms',true)")
    conn.execute("select public.medops_acquire_output_fence()")


def directory_user(conn: Any, expected: UserContext) -> UserContext | None:
    principal = PgDirectory(conn).resolve(expected.user_id)
    if principal is None or not principal.active:
        return None
    return UserContext(
        user_id=expected.user_id, dept=principal.dept, roles=principal.roles, acl_scopes=principal.scopes
    )


def require_same_user(expected: UserContext, current: UserContext | None) -> None:
    if current != expected:
        raise BusinessError(ErrorCode.forbidden, "execution identity is no longer authorized")


def validate_evidence(conn: Any, evidence: Sequence[Evidence], context: QueryContext) -> None:
    """All supplied snapshots are required: never silently drop one or replace its text.

    This includes evidence supporting a second-stage Skill conclusion, even when
    its Citation is omitted from the final report. Hash, Citation, status and
    historical marker must all agree; the normal fact-plane checks run again.
    """
    current = recheck_candidates(
        conn,
        [e.citation.chunk_id for e in evidence],
        as_of=context.as_of,
        allow_historical=context.historical_requested,
    )
    if current.rejected or tuple(evidence) != current.evidence:
        raise BusinessError(ErrorCode.evidence_integrity_failed, "final evidence changed or is no longer usable")
