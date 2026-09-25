"""DEC-013 envelope encryption: per-row DEK, versioned KEK, associated data binding, rotation by re-wrap."""

import base64
import json
import os
import secrets

import pytest

from medops.core.envelope import (
    LocalFileKeyProvider,
    PayloadIntegrityError,
    StaticKeyProvider,
    UnknownKeyVersion,
    open_sealed,
    payload_aad,
    rewrap,
    seal,
)

K1, K2 = secrets.token_bytes(32), secrets.token_bytes(32)


def test_roundtrip_binds_trace_node_and_kind_and_detects_tampering():
    provider = StaticKeyProvider({"k1": K1}, "k1")
    aad = payload_aad("a" * 32, "ask", "input")
    sealed = seal(b'{"query": "x"}', aad=aad, provider=provider)
    assert sealed.kek_version == "k1" and sealed.ciphertext != b'{"query": "x"}' and len(sealed.nonce) == 12
    assert open_sealed(sealed, aad=aad, provider=provider) == b'{"query": "x"}'
    with pytest.raises(PayloadIntegrityError):  # same blob presented as another trace / kind
        open_sealed(sealed, aad=payload_aad("b" * 32, "ask", "input"), provider=provider)
    flipped = sealed.__class__(
        bytes([sealed.ciphertext[0] ^ 1]) + sealed.ciphertext[1:], sealed.nonce, sealed.dek_wrapped, "k1"
    )
    with pytest.raises(PayloadIntegrityError):
        open_sealed(flipped, aad=aad, provider=provider)
    two = seal(b"same", aad=aad, provider=provider)
    assert two.ciphertext != seal(b"same", aad=aad, provider=provider).ciphertext  # fresh DEK and nonce every time


def test_rotation_rewraps_the_dek_without_touching_the_ciphertext():
    old = StaticKeyProvider({"k1": K1}, "k1")
    aad = payload_aad("a" * 32, "ask", "evidence_snapshot")
    sealed = seal(b"evidence", aad=aad, provider=old)
    rotated = StaticKeyProvider({"k1": K1, "k2": K2}, "k2")
    rewrapped = rewrap(sealed, provider=rotated)
    assert (
        rewrapped.kek_version == "k2"
        and rewrapped.ciphertext == sealed.ciphertext
        and rewrapped.dek_wrapped != sealed.dek_wrapped
    )
    assert open_sealed(rewrapped, aad=aad, provider=rotated) == b"evidence"
    retired = StaticKeyProvider({"k2": K2}, "k2")  # k1 gone: the old wrap is unreadable, the new one fine
    with pytest.raises(UnknownKeyVersion):
        open_sealed(sealed, aad=aad, provider=retired)
    assert open_sealed(rewrapped, aad=aad, provider=retired) == b"evidence"
    with pytest.raises(PayloadIntegrityError):  # wrong key under the same version name
        open_sealed(sealed, aad=aad, provider=StaticKeyProvider({"k1": K2}, "k1"))


def test_local_key_file_requires_private_permissions_and_32_byte_keys(tmp_path):
    path = tmp_path / "kek.json"
    path.write_text(json.dumps({"current": "k1", "keys": {"k1": base64.b64encode(K1).decode()}}))
    os.chmod(path, 0o644)
    with pytest.raises(PermissionError):
        LocalFileKeyProvider(path)
    os.chmod(path, 0o600)
    provider = LocalFileKeyProvider(path)
    assert provider.current() == ("k1", K1) and provider.key("k1") == K1
    path.write_text(json.dumps({"current": "k1", "keys": {"k1": base64.b64encode(b"short").decode()}}))
    with pytest.raises(ValueError):
        LocalFileKeyProvider(path)
