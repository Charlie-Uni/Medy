"""Short privileged sessions: current identity, target database and commit-bound fence."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal

from fastapi import Request

from medops.api.ports import ApiRuntime
from medops.application.metrics import has_role
from medops.core.errors import BusinessError, ErrorCode
from medops.domain.identity import UserContext


@contextmanager
def privileged_connection(
    runtime: ApiRuntime,
    request: Request,
    *roles: str,
    kind: Literal["admin", "restricted"] = "admin",
    mutation: bool = False,
) -> Iterator[tuple[UserContext, Any]]:
    """Authenticate before opening an elevated connection, then revalidate under its fence."""
    authorization = request.headers.get("authorization")
    with runtime.connection() as identity:
        user = runtime.authenticator.authenticate(authorization, runtime.directory(identity))
        if not has_role(user.roles, *roles):
            raise BusinessError(ErrorCode.forbidden, f"requires one of the roles: {', '.join(roles)}")
        connection = runtime.admin_connection if kind == "admin" else runtime.restricted_connection
        with connection() as target:
            runtime.validate_privileged_access(identity, target, user, authorization=authorization, mutation=mutation)
            yield user, target
