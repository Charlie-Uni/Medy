"""Bearer verification and principal resolution (M3-05): issuer, audience, expiry, signature and key id are all
checked; identity never comes from the request; unknown or inactive principals are refused; group claims add
scopes only through the allowlist."""

from __future__ import annotations

import pytest

from medops.api.auth import Authenticator, JwtVerifier, Principal, StaticDirectory, pseudonym
from medops.core.errors import BusinessError, ErrorCode
from medops.domain.common import Dept
from tests.unit.api._auth_fixtures import AUDIENCE, ISSUER, PSEUDONYM_KEY, TestIssuer

ISSUER_OBJ = TestIssuer()


def verifier(jwks=None) -> JwtVerifier:
    return JwtVerifier(issuer=ISSUER, audience=AUDIENCE, jwks=jwks or ISSUER_OBJ.jwks)


def directory(sub="user-1", dept=Dept.PV, active=True, scopes=frozenset({"PV:read"})) -> StaticDirectory:
    return StaticDirectory(
        {pseudonym(sub, PSEUDONYM_KEY): Principal(dept=dept, roles=("analyst",), scopes=scopes, active=active)}
    )


def test_valid_token_resolves_to_a_pseudonymous_user_context():
    auth = Authenticator(verifier=verifier(), pseudonym_key=PSEUDONYM_KEY)
    user = auth.authenticate("Bearer " + ISSUER_OBJ.token(), directory())
    assert user.dept is Dept.PV and user.acl_scopes == frozenset({"PV:read"}) and user.roles == ("analyst",)
    assert user.user_id == pseudonym("user-1", PSEUDONYM_KEY)[:32] and "user-1" not in user.user_id


@pytest.mark.parametrize(
    "kwargs",
    [
        {"issuer": "https://other.test"},
        {"audience": "someone-else"},
        {"exp_in": -120},
        {"kid": "unknown"},
        {"algorithm": "HS256"},
    ],
)
def test_bad_issuer_audience_expiry_key_or_algorithm_is_unauthenticated(kwargs):
    auth = Authenticator(verifier=verifier(), pseudonym_key=PSEUDONYM_KEY)
    if kwargs.get("algorithm") == "HS256":
        import jwt as pyjwt

        token = pyjwt.encode(
            {"sub": "user-1", "iss": ISSUER, "aud": AUDIENCE, "exp": 4102444800},
            "secret",
            algorithm="HS256",
            headers={"kid": "k1"},
        )
    else:
        token = ISSUER_OBJ.token(**kwargs)
    with pytest.raises(BusinessError) as exc:
        auth.authenticate("Bearer " + token, directory())
    assert exc.value.code is ErrorCode.unauthenticated


def test_signature_from_another_key_is_rejected():
    other = TestIssuer(kid="k1")  # same kid, different key
    auth = Authenticator(verifier=verifier(), pseudonym_key=PSEUDONYM_KEY)
    with pytest.raises(BusinessError) as exc:
        auth.authenticate("Bearer " + other.token(), directory())
    assert exc.value.code is ErrorCode.unauthenticated


@pytest.mark.parametrize("header", [None, "", "Basic abc", "Bearer", "Bearer   "])
def test_missing_or_malformed_authorization_is_unauthenticated(header):
    auth = Authenticator(verifier=verifier(), pseudonym_key=PSEUDONYM_KEY)
    with pytest.raises(BusinessError) as exc:
        auth.authenticate(header, directory())
    assert exc.value.code is ErrorCode.unauthenticated


def test_unknown_or_inactive_principal_is_forbidden_by_default():
    auth = Authenticator(verifier=verifier(), pseudonym_key=PSEUDONYM_KEY)
    with pytest.raises(BusinessError) as exc:
        auth.authenticate("Bearer " + ISSUER_OBJ.token(sub="stranger"), directory())
    assert exc.value.code is ErrorCode.forbidden
    with pytest.raises(BusinessError) as exc2:
        auth.authenticate("Bearer " + ISSUER_OBJ.token(), directory(active=False))
    assert exc2.value.code is ErrorCode.forbidden


def test_group_claims_add_scopes_only_through_the_allowlist():
    auth = Authenticator(verifier=verifier(), pseudonym_key=PSEUDONYM_KEY, group_scopes={"pv-analysts": ["PV:export"]})
    token = ISSUER_OBJ.token(extra={"groups": ["pv-analysts", "admins", "MA:read"]})
    user = auth.authenticate("Bearer " + token, directory())
    assert user.acl_scopes == frozenset({"PV:read", "PV:export"})  # 'admins' and a raw scope-looking group are ignored


def test_pseudonym_is_keyed_and_stable():
    a, b = pseudonym("user-1", b"k1"), pseudonym("user-1", b"k2")
    assert a != b and a == pseudonym("user-1", b"k1") and len(a) == 64
    with pytest.raises(ValueError):
        pseudonym("user-1", b"")
