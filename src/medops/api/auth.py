"""Request identity (M3-05; ADR-0001, INV-AUTH-01, INV-OBS-02).

A bearer token is verified (issuer, audience, expiry, signature) and yields only `sub`. The caller's department,
roles and scopes come from the server-side principal directory, keyed by the HMAC-SHA-256 pseudonym of `sub`;
IdP group claims add scopes only through an explicit allowlist. Unknown or inactive principals are refused
(default deny). Nothing in a request body or query can declare identity: `UserContext` is built here only.
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

import jwt
from jwt import PyJWKSet

from medops.core.errors import BusinessError, ErrorCode
from medops.domain.common import Dept, DomainModel
from medops.domain.identity import Scope, UserContext

ALGORITHMS: tuple[str, ...] = ("RS256", "ES256")
REQUIRED_CLAIMS: tuple[str, ...] = ("exp", "iss", "aud", "sub")


class Principal(DomainModel):
    dept: Dept
    roles: tuple[str, ...] = ()
    scopes: frozenset[Scope] = frozenset()
    active: bool = True


class PrincipalDirectory(Protocol):
    def resolve(self, pseudonym: str) -> Principal | None: ...


class StaticDirectory:
    """Dev/test directory: synthetic identities only (ADR-0001 §4)."""

    def __init__(self, principals: Mapping[str, Principal]) -> None:
        self._p = dict(principals)

    def resolve(self, pseudonym: str) -> Principal | None:
        return self._p.get(pseudonym)


class PgDirectory:
    """The `principals` table (migration 0009), read under the application role before the department is injected."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def resolve(self, pseudonym: str) -> Principal | None:
        row = self._conn.execute(
            "select dept::text, roles, scopes, active from principals where sub_pseudonym = %s", (pseudonym,)
        ).fetchone()
        if row is None:
            return None
        dept, roles, scopes, active = row
        return Principal(dept=Dept(dept), roles=tuple(roles), scopes=frozenset(scopes), active=bool(active))


def pseudonym(sub: str, key: bytes) -> str:
    """Keyed pseudonym of the token subject (INV-OBS-02: never an unsalted hash, supports key rotation by key)."""
    if not key:
        raise ValueError("identity pseudonym key must not be empty")
    return hmac.new(key, sub.encode("utf-8"), hashlib.sha256).hexdigest()


class TokenVerifier(Protocol):
    def verify(self, token: str) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class JwtVerifier:
    """OIDC-compatible bearer verification against a JWK set: issuer, audience, expiry and signature are all
    required (ADR-0001 §1). Keys are looked up by `kid`; unknown kids are refused, never guessed."""

    issuer: str
    audience: str
    jwks: Mapping[str, Any]
    algorithms: tuple[str, ...] = ALGORITHMS
    leeway_s: int = 30
    _keys: dict[str, Any] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        keyset = PyJWKSet.from_dict(dict(self.jwks))
        object.__setattr__(self, "_keys", {k.key_id: k for k in keyset.keys if k.key_id})

    def verify(self, token: str) -> Mapping[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
            key = self._keys.get(header.get("kid") or "")
            if key is None:
                raise BusinessError(ErrorCode.unauthenticated, "token key is not trusted")
            if header.get("alg") not in self.algorithms:
                raise BusinessError(ErrorCode.unauthenticated, "token algorithm is not accepted")
            claims = jwt.decode(
                token,
                key=key.key,
                algorithms=list(self.algorithms),
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway_s,
                options={"require": list(REQUIRED_CLAIMS)},
            )
        except BusinessError:
            raise
        except jwt.PyJWTError as exc:
            raise BusinessError(ErrorCode.unauthenticated, "token rejected", detail=type(exc).__name__) from None
        if not isinstance(claims.get("sub"), str) or not claims["sub"]:
            raise BusinessError(ErrorCode.unauthenticated, "token has no subject")
        return claims


@dataclass(frozen=True)
class Authenticator:
    verifier: TokenVerifier
    pseudonym_key: bytes
    group_scopes: Mapping[str, Sequence[str]] = field(default_factory=dict)  # IdP group -> allowlisted scopes

    def authenticate(self, authorization: str | None, directory: PrincipalDirectory) -> UserContext:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise BusinessError(ErrorCode.unauthenticated, "bearer token required")
        token = authorization[7:].strip()
        if not token:
            raise BusinessError(ErrorCode.unauthenticated, "bearer token required")
        claims = self.verifier.verify(token)
        pid = pseudonym(str(claims["sub"]), self.pseudonym_key)
        principal = directory.resolve(pid)
        if principal is None or not principal.active:
            raise BusinessError(ErrorCode.forbidden, "principal is not provisioned for this service")
        scopes = set(principal.scopes)
        groups = claims.get("groups")
        if isinstance(groups, list):
            for group in groups:
                for scope in self.group_scopes.get(str(group), ()):
                    scopes.add(scope)  # only allowlisted groups map to scopes (ADR-0001 §3)
        # the full pseudonym is the principal key everywhere (directory, tasks, traces): never truncated
        return UserContext(user_id=pid, dept=principal.dept, roles=principal.roles, acl_scopes=frozenset(scopes))
