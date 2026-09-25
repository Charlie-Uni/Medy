"""Envelope encryption for restricted replay payloads (DEC-013, INV-OBS-03): every blob gets a fresh 256-bit DEK,
AES-256-GCM with a 12-byte nonce and the trace / node / kind as associated data; the DEK is wrapped with a versioned
KEK from a `KeyProvider`. Rotation re-wraps DEKs without touching ciphertexts. v1 provider = a local JSON key file
injected at deployment (never `.env`), KMS / Vault adapters plug in behind the same protocol."""

from __future__ import annotations

import base64
import json
import os
import secrets
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

KEY_BYTES = 32
NONCE_BYTES = 12


class KeyProvider(Protocol):
    def current(self) -> tuple[str, bytes]:
        """(kek_version, key) used for new wraps."""
        ...

    def key(self, version: str) -> bytes: ...


class UnknownKeyVersion(KeyError):
    pass


class PayloadIntegrityError(ValueError):
    """Ciphertext, nonce, wrapped DEK or associated data was altered (GCM tag mismatch)."""


@dataclass(frozen=True)
class StaticKeyProvider:
    keys: dict[str, bytes]
    current_version: str

    def current(self) -> tuple[str, bytes]:
        return self.current_version, self.keys[self.current_version]

    def key(self, version: str) -> bytes:
        try:
            return self.keys[version]
        except KeyError:
            raise UnknownKeyVersion(version) from None


class LocalFileKeyProvider:
    """JSON file `{"current": "k1", "keys": {"k1": "<base64 32 bytes>", ...}}`, mode 0600, owned by the process user."""

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self._path = Path(path)
        mode = stat.S_IMODE(self._path.stat().st_mode)
        if mode & 0o077:
            raise PermissionError(
                f"payload key file {self._path} must not be group/world accessible (mode {oct(mode)})"
            )
        data = json.loads(self._path.read_text(encoding="utf-8"))
        keys = {v: base64.b64decode(k) for v, k in data["keys"].items()}
        for version, raw in keys.items():
            if len(raw) != KEY_BYTES:
                raise ValueError(f"key {version} must be {KEY_BYTES} bytes")
        if data["current"] not in keys:
            raise ValueError("current key version is not in keys")
        self._static = StaticKeyProvider(keys, data["current"])

    def current(self) -> tuple[str, bytes]:
        return self._static.current()

    def key(self, version: str) -> bytes:
        return self._static.key(version)


@dataclass(frozen=True)
class Sealed:
    ciphertext: bytes
    nonce: bytes
    dek_wrapped: bytes  # nonce || AES-GCM(KEK, DEK)
    kek_version: str


def seal(plaintext: bytes, *, aad: bytes, provider: KeyProvider) -> Sealed:
    version, kek = provider.current()
    dek = secrets.token_bytes(KEY_BYTES)
    nonce = secrets.token_bytes(NONCE_BYTES)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, aad)
    wrap_nonce = secrets.token_bytes(NONCE_BYTES)
    dek_wrapped = wrap_nonce + AESGCM(kek).encrypt(wrap_nonce, dek, version.encode("utf-8"))
    return Sealed(ciphertext, nonce, dek_wrapped, version)


def _unwrap(sealed: Sealed, provider: KeyProvider) -> bytes:
    kek = provider.key(sealed.kek_version)
    try:
        return AESGCM(kek).decrypt(
            sealed.dek_wrapped[:NONCE_BYTES], sealed.dek_wrapped[NONCE_BYTES:], sealed.kek_version.encode("utf-8")
        )
    except InvalidTag:
        raise PayloadIntegrityError("wrapped DEK does not verify under the recorded KEK version") from None


def open_sealed(sealed: Sealed, *, aad: bytes, provider: KeyProvider) -> bytes:
    dek = _unwrap(sealed, provider)
    try:
        return AESGCM(dek).decrypt(sealed.nonce, sealed.ciphertext, aad)
    except InvalidTag:
        raise PayloadIntegrityError("payload ciphertext or associated data does not verify") from None


def rewrap(sealed: Sealed, *, provider: KeyProvider) -> Sealed:
    """Key rotation: wrap the same DEK under the provider's current KEK; the ciphertext is untouched."""
    dek = _unwrap(sealed, provider)
    version, kek = provider.current()
    wrap_nonce = secrets.token_bytes(NONCE_BYTES)
    return Sealed(
        sealed.ciphertext,
        sealed.nonce,
        wrap_nonce + AESGCM(kek).encrypt(wrap_nonce, dek, version.encode("utf-8")),
        version,
    )


def payload_aad(trace_id: str, node: str, kind: str) -> bytes:
    return f"{trace_id}|{node}|{kind}".encode()
