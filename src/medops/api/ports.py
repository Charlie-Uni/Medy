"""Environment contract used by API routes; independent of the application factory."""

from __future__ import annotations

from contextlib import AbstractContextManager
from typing import Any, Protocol

from medops.api.auth import Authenticator, PrincipalDirectory
from medops.api.contracts import (
    AskRequest,
)
from medops.application.admin import (
    DocumentActions,
    DocumentAdminStore,
    PolicyStore,
    ReceiptStore,
)
from medops.application.audit import TraceStore
from medops.application.metrics import MetricsSource
from medops.application.payloads import PayloadReader, PayloadWriter
from medops.application.policy_loader import RequestPolicies
from medops.application.tasks import TaskStore
from medops.domain.identity import UserContext
from medops.domain.state import VersionSet
from medops.harness.dependencies import HarnessDeps


class ApiRuntime(Protocol):
    """What the routes need from the environment; production wires PostgreSQL, the retrieval stack and the
    gateway, tests wire fakes. `connection()` must yield a connection inside a transaction that is committed
    on normal exit and rolled back on error."""

    authenticator: Authenticator
    versions: VersionSet

    def connection(self) -> AbstractContextManager[Any]: ...

    def directory(self, conn: Any) -> PrincipalDirectory: ...

    def bind_identity(self, conn: Any, user: UserContext) -> None: ...

    def route_policies(self, conn: Any, user: UserContext) -> RequestPolicies: ...

    def build_deps(
        self, conn: Any, user: UserContext, request: AskRequest, routed: RequestPolicies | None = None
    ) -> HarnessDeps: ...

    def task_store(self, conn: Any) -> TaskStore: ...

    def trace_store(self, conn: Any) -> TraceStore: ...

    def metrics_source(self, conn: Any) -> MetricsSource: ...

    def resolve_user(self, conn: Any, principal: str) -> UserContext | None: ...

    # M3-03 admin routes run on the admin database role (INV-AUTH-05: separated roles); the unit-test runtime yields None
    def admin_connection(self) -> AbstractContextManager[Any]: ...

    def document_admin(self, conn: Any) -> tuple[DocumentAdminStore, DocumentActions]: ...

    def policy_store(self, conn: Any) -> PolicyStore: ...

    def receipt_store(self, conn: Any) -> ReceiptStore | None: ...

    # M3-07 restricted payloads (DEC-013): writer on the request connection (None = disabled), reader on the restricted role
    def payload_writer(self, conn: Any) -> PayloadWriter | None: ...

    def restricted_connection(self) -> AbstractContextManager[Any]: ...

    def payload_reader(self, conn: Any) -> PayloadReader: ...

    @property
    def monthly_cap_usd(self) -> float | None: ...

    def ready(self) -> bool: ...
