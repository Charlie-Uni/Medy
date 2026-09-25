"""KEK rotation for encrypted replay payloads (M5-06, record 87; DEC-013).

Rotation never touches ciphertext: every row's random DEK is unwrapped under the KEK version recorded on the row and
wrapped again under the key file's `current` version (`medops.core.envelope.rewrap`). Runs on the restricted role,
which migration 0019 allows to update exactly `dek_wrapped` and `kek_version`; the trigger refuses anything else.
Procedure (docs/OPERATIONS.md): add the new key to the key file, set it as `current`, run this until `stale == 0`,
then remove the old key from the file. The DEKs live in process memory only during the rewrap; no access-log row is
written because no payload is decrypted.

    python -m medops.application.payload_rotation [--batch 500] [--dry-run]   (DATABASE_RESTRICTED_URL + PAYLOAD_KEY_FILE)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from typing import Any

from medops.core.envelope import KeyProvider, Sealed, rewrap
from medops.infrastructure.db.payloads import PgPayloadStore


@dataclass
class RotationReport:
    current_version: str
    stale_before: int
    rewrapped: int
    dry_run: bool


def rotate(conn: Any, provider: KeyProvider, *, batch: int = 500, dry_run: bool = False) -> RotationReport:
    store = PgPayloadStore(conn)
    current, _ = provider.current()
    stale_before = store.count_stale(current)
    rewrapped = 0
    while True:
        rows = store.stale(current, limit=batch)
        if not rows:
            break
        for row in rows:
            sealed = Sealed(row["ciphertext"], row["nonce"], row["dek_wrapped"], row["kek_version"])
            fresh = rewrap(sealed, provider=provider)
            if not dry_run:
                store.rewrap_row(row["payload_id"], fresh)
            rewrapped += 1
        if dry_run:
            break
    return RotationReport(current_version=current, stale_before=stale_before, rewrapped=rewrapped, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    import psycopg

    from medops.core.config import Settings
    from medops.core.envelope import LocalFileKeyProvider

    settings = Settings()  # type: ignore[call-arg]
    ap = argparse.ArgumentParser(description="rewrap payload DEKs under the current KEK (restricted role)")
    ap.add_argument("--batch", type=int, default=500)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    if settings.database_restricted_url is None or not settings.payload_key_file:
        print("DATABASE_RESTRICTED_URL and PAYLOAD_KEY_FILE are required", file=sys.stderr)
        return 2
    provider = LocalFileKeyProvider(settings.payload_key_file)
    with psycopg.connect(
        settings.database_restricted_url.get_secret_value(),
        connect_timeout=settings.db_connect_timeout_s,
        options=f"-c statement_timeout={settings.db_statement_timeout_ms}",
    ) as conn:
        with conn.transaction():
            report = rotate(conn, provider, batch=args.batch, dry_run=args.dry_run)
            if args.dry_run:
                conn.rollback()
    print(json.dumps(asdict(report)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
