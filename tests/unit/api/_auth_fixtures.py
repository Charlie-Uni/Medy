"""Synthetic issuer for API tests (ADR-0001 §4): a fresh RSA key, a JWKS document and signed tokens."""

from __future__ import annotations

import json
import time
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

ISSUER = "https://issuer.test/medops"
AUDIENCE = "medops-api"
PSEUDONYM_KEY = b"test-pseudonym-key"


class TestIssuer:
    __test__ = False  # not a pytest collectable

    def __init__(self, kid: str = "k1") -> None:
        self.kid = kid
        self.private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public = json.loads(RSAAlgorithm.to_jwk(self.private.public_key()))
        public.update({"kid": kid, "use": "sig", "alg": "RS256"})
        self.jwks: dict[str, Any] = {"keys": [public]}

    def token(
        self,
        sub: str = "user-1",
        *,
        issuer: str = ISSUER,
        audience: str = AUDIENCE,
        exp_in: int = 600,
        kid: str | None = None,
        algorithm: str = "RS256",
        extra: dict[str, Any] | None = None,
    ) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {"sub": sub, "iss": issuer, "aud": audience, "iat": now, "exp": now + exp_in}
        claims.update(extra or {})
        return jwt.encode(claims, self.private, algorithm=algorithm, headers={"kid": kid or self.kid})
