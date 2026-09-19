"""Caller identity as resolved server-side from a verified token (INV-AUTH-01)."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, field_serializer

from medops.domain.common import Dept, DomainModel, NonEmptyStr

Scope = Annotated[str, Field(pattern=r"^(MA|PV|CO|ADMIN):[a-z_]+$")]


class UserContext(DomainModel):
    user_id: NonEmptyStr  # surrogate id or HMAC pseudonym, never a raw identity (INV-OBS-02)
    dept: Dept
    roles: tuple[NonEmptyStr, ...] = ()
    acl_scopes: frozenset[Scope] = frozenset()

    @field_serializer("acl_scopes")
    def _sorted_scopes(self, scopes: frozenset[str]) -> list[str]:
        """Sets iterate in hash order, which differs across processes; serialize sorted so that
        dumps, canonical hashes and operation keys are stable (baseline 3.2)."""
        return sorted(scopes)

    def has_scopes(self, required: tuple[str, ...]) -> bool:
        """Registry check: every required scope must be held (INV-AUTH-03); default deny."""
        return all(scope in self.acl_scopes for scope in required)
