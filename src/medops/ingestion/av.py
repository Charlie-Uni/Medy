"""Optional antivirus hook: ClamAV `clamd` INSTREAM scanning (ADR-0009 §4).

The protocol is small enough to implement here (no client dependency): `zINSTREAM\\0`, then chunks framed
by a 4-byte big-endian length, a zero-length chunk to finish, and one NUL-terminated reply
(`stream: OK` or `stream: <signature> FOUND`). Fixed connect/read timeouts (INV-HAR-04). Any failure to obtain
a verdict is `ScanUnavailable`; the pipeline fails closed when a scanner is configured.
"""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlsplit

CHUNK_BYTES = 64 * 1024


class ScanUnavailable(Exception):
    """No verdict could be obtained (connection, timeout, protocol)."""


@dataclass(frozen=True)
class ScanVerdict:
    status: str  # "clean" | "infected" | "skipped"
    scanner: str
    signature: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {"status": self.status, "scanner": self.scanner, "signature": self.signature}


class Scanner(Protocol):
    def scan(self, data: bytes) -> ScanVerdict: ...


class NoScanner:
    """Records that no antivirus scan ran (dev/test without clamd); prod configuration forbids this."""

    def scan(self, data: bytes) -> ScanVerdict:
        return ScanVerdict("skipped", "none")


class ClamdScanner:
    def __init__(self, address: str, *, timeout: float = 30.0) -> None:
        parts = urlsplit(address)
        if parts.scheme == "tcp" and parts.hostname and parts.port:
            self._target: tuple[str, int] | str = (parts.hostname, parts.port)
        elif parts.scheme == "unix" and parts.path:
            self._target = parts.path
        else:
            raise ValueError("clamd address must be tcp://host:port or unix:///path")
        self._timeout = timeout
        self.name = f"clamd@{address}"

    def _connect(self) -> socket.socket:
        if isinstance(self._target, tuple):
            return socket.create_connection(self._target, timeout=self._timeout)
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(self._timeout)
        sock.connect(self._target)
        return sock

    def scan(self, data: bytes) -> ScanVerdict:
        try:
            with self._connect() as sock:
                sock.sendall(b"zINSTREAM\0")
                for start in range(0, len(data), CHUNK_BYTES):
                    part = data[start : start + CHUNK_BYTES]
                    sock.sendall(struct.pack("!I", len(part)) + part)
                sock.sendall(struct.pack("!I", 0))
                reply = b""
                while not reply.endswith(b"\0"):
                    got = sock.recv(4096)
                    if not got:
                        break
                    reply += got
                    if len(reply) > 65536:
                        raise ScanUnavailable("clamd reply too long")
        except (OSError, struct.error) as exc:
            raise ScanUnavailable(type(exc).__name__) from None
        text = reply.rstrip(b"\0").decode("utf-8", errors="replace").strip()
        if text.endswith(" OK"):
            return ScanVerdict("clean", self.name)
        if text.endswith(" FOUND"):
            signature = text.split(":", 1)[-1].strip()[: -len(" FOUND")].strip()
            return ScanVerdict("infected", self.name, signature or "unknown")
        raise ScanUnavailable(f"unexpected clamd reply: {text[:60]!r}")
