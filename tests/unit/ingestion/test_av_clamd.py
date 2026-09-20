"""clamd INSTREAM client against a local fake server: framing (length-prefixed chunks, zero terminator),
clean/infected verdicts, unavailable server and malformed replies; plus the recorded 'skipped' verdict."""

from __future__ import annotations

import socket
import struct
import threading
from collections.abc import Iterator

import pytest

from medops.ingestion.av import ClamdScanner, NoScanner, ScanUnavailable


class FakeClamd:
    def __init__(self, reply: bytes | None = None) -> None:
        self.sock = socket.socket()
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.reply = reply
        self.received: list[bytes] = []
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    @property
    def address(self) -> str:
        return f"tcp://127.0.0.1:{self.sock.getsockname()[1]}"

    def _serve(self) -> None:
        conn, _ = self.sock.accept()
        with conn:
            buf = b""
            while b"\0" not in buf:
                buf += conn.recv(4096)
            command, buf = buf.split(b"\0", 1)
            assert command == b"zINSTREAM"
            data = b""
            while True:
                while len(buf) < 4:
                    buf += conn.recv(4096)
                (n,) = struct.unpack("!I", buf[:4])
                buf = buf[4:]
                if n == 0:
                    break
                while len(buf) < n:
                    buf += conn.recv(4096)
                data += buf[:n]
                buf = buf[n:]
            self.received.append(data)
            if self.reply is None:
                reply = b"stream: Eicar-Test-Signature FOUND\0" if b"EICAR" in data else b"stream: OK\0"
            else:
                reply = self.reply
            conn.sendall(reply)

    def close(self) -> None:
        self.sock.close()


@pytest.fixture
def server() -> Iterator[FakeClamd]:
    s = FakeClamd()
    yield s
    s.close()


def test_clean_and_infected_verdicts_and_exact_streaming(server):
    scanner = ClamdScanner(server.address, timeout=5)
    payload = bytes(range(256)) * 700  # crosses the 64 KiB chunk boundary
    verdict = scanner.scan(payload)
    assert verdict.status == "clean" and verdict.signature is None and server.received == [payload]
    server2 = FakeClamd()
    try:
        infected = ClamdScanner(server2.address, timeout=5).scan(
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        )
        assert infected.status == "infected" and infected.signature == "Eicar-Test-Signature"
    finally:
        server2.close()


def test_unavailable_server_and_malformed_reply_raise():
    with pytest.raises(ScanUnavailable):
        ClamdScanner("tcp://127.0.0.1:1", timeout=0.5).scan(b"data")
    odd = FakeClamd(reply=b"stream: ??? \0")
    try:
        with pytest.raises(ScanUnavailable, match="unexpected"):
            ClamdScanner(odd.address, timeout=5).scan(b"data")
    finally:
        odd.close()
    with pytest.raises(ValueError):
        ClamdScanner("http://x:1")


def test_no_scanner_records_skipped():
    v = NoScanner().scan(b"x")
    assert v.as_dict() == {"status": "skipped", "scanner": "none", "signature": None}
