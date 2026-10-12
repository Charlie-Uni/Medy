"""Shared replay runtime test support; no collected test cases."""

from __future__ import annotations

from medops.domain.common import Dept
from medops.domain.identity import UserContext
from medops.infrastructure.identity import Principal, StaticDirectory, pseudonym
from tests.support.api_runtime import ISSUER_OBJ, FakeRuntime
from tests.support.identity import PSEUDONYM_KEY

USER_PID = pseudonym("user-1", PSEUDONYM_KEY)


ADMIN_PID = pseudonym("admin-1", PSEUDONYM_KEY)


class ReplayRuntime(FakeRuntime):
    def directory(self, conn):
        return StaticDirectory(
            {
                USER_PID: Principal(dept=Dept.MA, roles=("analyst",), scopes=frozenset({"MA:read"})),
                ADMIN_PID: Principal(dept=Dept.MA, roles=("admin",), scopes=frozenset({"MA:read"})),
            }
        )

    def resolve_user(self, conn, principal):
        p = self.directory(conn).resolve(principal)
        if p is None or principal != USER_PID:
            return None
        return UserContext(user_id=principal, dept=p.dept, roles=p.roles, acl_scopes=p.scopes)


def auth(sub: str) -> dict[str, str]:
    return {"Authorization": "Bearer " + ISSUER_OBJ.token(sub=sub)}
