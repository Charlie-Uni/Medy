"""Client-side credentials for local API evaluation and demo tools."""

from __future__ import annotations

import time

import jwt


def issue_demo_token(pem: bytes, *, kid: str, issuer: str, audience: str, sub: str) -> str:
    """Sign the existing one-hour demo token; callers supply the synthetic issuer key.

    Claims identify a principal only. The API still resolves roles and department from its
    directory. This helper does not load keys, persist tokens or configure server authentication.
    """
    now = int(time.time())
    return jwt.encode(
        {"sub": sub, "iss": issuer, "aud": audience, "iat": now, "exp": now + 3600},
        pem,
        algorithm="RS256",
        headers={"kid": kid},
    )
