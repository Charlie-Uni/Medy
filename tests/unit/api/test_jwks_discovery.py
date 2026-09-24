"""RemoteJwks (M3-05): keys come from OIDC discovery or an explicit JWKS URL, are cached, refreshed once for an
unknown kid (rotation), throttled against refresh floods, and a fetch failure is a dependency outage rather
than an authentication verdict."""

from __future__ import annotations

import json

import httpx
import pytest

from medops.api.auth import Authenticator, JwtVerifier, Principal, RemoteJwks, StaticDirectory, pseudonym
from medops.core.errors import BusinessError, ErrorCode, InfrastructureError
from medops.domain.common import Dept
from tests.unit.api._auth_fixtures import AUDIENCE, ISSUER, PSEUDONYM_KEY, TestIssuer


class FakeIdp:
    def __init__(self, issuers: list[TestIssuer]):
        self.issuers = issuers
        self.hits: list[str] = []
        self.down = False

    def transport(self) -> httpx.MockTransport:
        def handler(request: httpx.Request) -> httpx.Response:
            self.hits.append(request.url.path)
            if self.down:
                return httpx.Response(503, text="idp down")
            if request.url.path.endswith("/.well-known/openid-configuration"):
                return httpx.Response(200, json={"issuer": ISSUER, "jwks_uri": ISSUER + "/keys"})
            if request.url.path.endswith("/keys"):
                return httpx.Response(200, json={"keys": [k for i in self.issuers for k in i.jwks["keys"]]})
            return httpx.Response(404)

        return httpx.MockTransport(handler)


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def directory() -> StaticDirectory:
    return StaticDirectory({pseudonym("user-1", PSEUDONYM_KEY): Principal(dept=Dept.PV, scopes=frozenset({"PV:read"}))})


def make(idp: FakeIdp, clock: Clock, ttl: float = 3600.0) -> tuple[Authenticator, RemoteJwks]:
    source = RemoteJwks(ISSUER, client=httpx.Client(transport=idp.transport()), ttl_s=ttl, clock=clock)
    return Authenticator(
        verifier=JwtVerifier(issuer=ISSUER, audience=AUDIENCE, key_source=source), pseudonym_key=PSEUDONYM_KEY
    ), source


def test_discovery_then_jwks_are_fetched_once_and_cached():
    k1 = TestIssuer("k1")
    idp = FakeIdp([k1])
    auth, _ = make(idp, Clock())
    for _ in range(3):
        assert auth.authenticate("Bearer " + k1.token(), directory()).dept is Dept.PV
    assert idp.hits == ["/medops/.well-known/openid-configuration", "/medops/keys"]  # one discovery, one JWKS fetch


def test_key_rotation_refreshes_once_and_unknown_kids_are_refused_after_that():
    k1, k2 = TestIssuer("k1"), TestIssuer("k2")
    idp = FakeIdp([k1])
    clock = Clock()
    auth, _ = make(idp, clock)
    auth.authenticate("Bearer " + k1.token(), directory())
    idp.issuers.append(k2)  # the IdP rotates in a new key
    assert auth.authenticate("Bearer " + k2.token(), directory()).dept is Dept.PV  # unknown kid -> one refresh -> found
    assert idp.hits.count("/medops/keys") == 2
    stranger = TestIssuer("k9")
    with pytest.raises(BusinessError) as exc:
        auth.authenticate("Bearer " + stranger.token(), directory())
    assert exc.value.code is ErrorCode.unauthenticated
    assert idp.hits.count("/medops/keys") == 2  # refresh throttled: the flood of unknown kids does not hammer the IdP
    clock.t += 60
    with pytest.raises(BusinessError):
        auth.authenticate("Bearer " + stranger.token(), directory())
    assert idp.hits.count("/medops/keys") == 3  # after the gap one more refresh is allowed, still refused


def test_ttl_expiry_refreshes_and_idp_outage_is_a_dependency_error():
    k1 = TestIssuer("k1")
    idp = FakeIdp([k1])
    clock = Clock()
    auth, _ = make(idp, clock, ttl=100)
    auth.authenticate("Bearer " + k1.token(), directory())
    clock.t += 200
    auth.authenticate("Bearer " + k1.token(), directory())
    assert idp.hits.count("/medops/keys") == 2
    idp.down = True
    clock.t += 200
    with pytest.raises(InfrastructureError) as exc:
        auth.authenticate("Bearer " + k1.token(), directory())
    assert exc.value.code is ErrorCode.dependency_unavailable and exc.value.retryable


def test_explicit_jwks_url_skips_discovery_and_verifier_needs_exactly_one_source():
    k1 = TestIssuer("k1")
    idp = FakeIdp([k1])
    source = RemoteJwks(ISSUER, jwks_url=ISSUER + "/keys", client=httpx.Client(transport=idp.transport()))
    auth = Authenticator(
        verifier=JwtVerifier(issuer=ISSUER, audience=AUDIENCE, key_source=source), pseudonym_key=PSEUDONYM_KEY
    )
    auth.authenticate("Bearer " + k1.token(), directory())
    assert idp.hits == ["/medops/keys"]
    with pytest.raises(ValueError):
        JwtVerifier(issuer=ISSUER, audience=AUDIENCE)
    with pytest.raises(ValueError):
        JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=k1.jwks, key_source=source)
    assert json.loads(json.dumps(k1.jwks))["keys"][0]["kid"] == "k1"
