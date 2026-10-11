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

from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
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


class KeySource(Protocol):
    def keys(self, *, refresh: bool = False) -> Mapping[str, Any]:
        """kid -> PyJWK. `refresh=True` asks a remote source to re-fetch (key rotation: an unknown kid)."""
        ...


class StaticJwks:
    """A JWK set given as configuration (dev/test issuer, or an operator-managed copy)."""

    def __init__(self, jwks: Mapping[str, Any]) -> None:
        keyset = PyJWKSet.from_dict(dict(jwks))
        self._keys = {k.key_id: k for k in keyset.keys if k.key_id}

    def keys(self, *, refresh: bool = False) -> Mapping[str, Any]:
        return self._keys


class RemoteJwks:
    """JWKS fetched from the issuer (OIDC discovery `/.well-known/openid-configuration` -> `jwks_uri`, or an explicit
    URL), cached for `ttl_s` and refreshed at most once per unknown kid. Fetch failures are a dependency outage
    (`503 dependency_unavailable`), never an authentication verdict."""

    def __init__(
        self,
        issuer: str,
        *,
        jwks_url: str | None = None,
        client: Any | None = None,
        ttl_s: float = 3600.0,
        clock: Any = None,
    ) -> None:
        import time

        import httpx

        self._issuer = issuer.rstrip("/")
        self._jwks_url = jwks_url
        self._client = client or httpx.Client(timeout=5.0)
        self._ttl = ttl_s
        self._clock = clock or time.monotonic
        self._keys: dict[str, Any] = {}
        self._fetched_at: float | None = None
        self._min_refresh_gap_s = 30.0
        self._last_refresh: float = float("-inf")

    def _fetch(self) -> None:
        import httpx

        try:
            if self._jwks_url is None:
                doc = self._client.get(f"{self._issuer}/.well-known/openid-configuration")
                doc.raise_for_status()
                self._jwks_url = str(doc.json()["jwks_uri"])
            response = self._client.get(self._jwks_url)
            response.raise_for_status()
            keyset = PyJWKSet.from_dict(response.json())
        except (httpx.HTTPError, KeyError, ValueError, TypeError) as exc:
            raise InfrastructureError(
                ErrorCode.dependency_unavailable, detail=f"jwks fetch failed: {type(exc).__name__}", retryable=True
            ) from None
        self._keys = {k.key_id: k for k in keyset.keys if k.key_id}
        self._fetched_at = self._clock()

    def keys(self, *, refresh: bool = False) -> Mapping[str, Any]:
        now = self._clock()
        stale = self._fetched_at is None or now - self._fetched_at > self._ttl
        if refresh and now - self._last_refresh < self._min_refresh_gap_s and not stale:
            return self._keys  # do not let a flood of unknown kids hammer the issuer
        if stale or refresh:
            if refresh:
                self._last_refresh = now
            self._fetch()
        return self._keys


class JwtVerifier:
    """OIDC-compatible bearer verification: issuer, audience, expiry and signature are all required (ADR-0001 §1).
    Keys are looked up by `kid`; an unknown kid triggers one refresh of a remote source (rotation) and is
    otherwise refused, never guessed."""

    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        jwks: Mapping[str, Any] | None = None,
        key_source: KeySource | None = None,
        algorithms: tuple[str, ...] = ALGORITHMS,
        leeway_s: int = 30,
    ) -> None:
        if (jwks is None) == (key_source is None):
            raise ValueError("JwtVerifier needs exactly one of jwks or key_source")
        self.issuer = issuer
        self.audience = audience
        self.algorithms = algorithms
        self.leeway_s = leeway_s
        self._source: KeySource = key_source if key_source is not None else StaticJwks(jwks or {})

    def verify(self, token: str) -> Mapping[str, Any]:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise BusinessError(ErrorCode.unauthenticated, "token rejected", detail=type(exc).__name__) from None
        kid = header.get("kid") or ""
        key = self._source.keys().get(kid)
        if key is None and kid:
            key = self._source.keys(refresh=True).get(kid)  # rotation: one refresh, then refuse
        if key is None:
            raise BusinessError(ErrorCode.unauthenticated, "token key is not trusted")
        if header.get("alg") not in self.algorithms:
            raise BusinessError(ErrorCode.unauthenticated, "token algorithm is not accepted")
        try:
            claims = jwt.decode(
                token,
                key=key.key,
                algorithms=list(self.algorithms),
                audience=self.audience,
                issuer=self.issuer,
                leeway=self.leeway_s,
                options={"require": list(REQUIRED_CLAIMS)},
            )
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
