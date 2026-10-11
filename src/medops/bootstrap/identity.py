"""OIDC configuration shared by HTTP and MCP entry points."""

import json

from medops.core.config import Settings
from medops.infrastructure.identity import Authenticator, JwtVerifier, RemoteJwks


def authenticator_from_settings(settings: Settings) -> Authenticator:
    """Keys come from `OIDC_JWKS_JSON` (static) or from the issuer (discovery / `OIDC_JWKS_URL`); the pseudonym key
    and issuer/audience are always required (ADR-0001)."""
    missing = [k for k in ("oidc_issuer", "oidc_audience", "identity_pseudonym_key") if getattr(settings, k) is None]
    if missing:
        raise ValueError(f"API identity boundary needs {', '.join(missing)} (ADR-0001)")
    assert settings.oidc_issuer and settings.oidc_audience and settings.identity_pseudonym_key
    if settings.oidc_jwks_json:
        verifier = JwtVerifier(
            issuer=settings.oidc_issuer, audience=settings.oidc_audience, jwks=json.loads(settings.oidc_jwks_json)
        )
    else:
        verifier = JwtVerifier(
            issuer=settings.oidc_issuer,
            audience=settings.oidc_audience,
            key_source=RemoteJwks(settings.oidc_issuer, jwks_url=settings.oidc_jwks_url),
        )
    groups = json.loads(settings.oidc_group_scopes_json) if settings.oidc_group_scopes_json else {}
    return Authenticator(
        verifier=verifier,
        pseudonym_key=settings.identity_pseudonym_key.get_secret_value().encode("utf-8"),
        group_scopes={str(k): [str(x) for x in v] for k, v in groups.items()},
    )
