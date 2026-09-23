"""`python -m medops.api.serve [--host 127.0.0.1] [--port 8000] [--device cpu|mps]`: the API over the production
runtime. Configuration comes from `Settings` (.env); production forbids docs and debug (baseline 5.12)."""

from __future__ import annotations

import argparse
import sys

from medops.api.app import create_app
from medops.api.runtime import ProductionRuntime
from medops.core.config import Settings, safe_config_errors
from medops.core.logging import configure_logging, get_logger


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args(argv)
    try:
        settings = Settings()  # type: ignore[call-arg]
    except Exception as exc:  # noqa: BLE001 - configuration errors are reported in their safe form only
        from pydantic import ValidationError

        detail = safe_config_errors(exc) if isinstance(exc, ValidationError) else [{"msg": type(exc).__name__}]
        print(f"configuration invalid: {detail}", file=sys.stderr)
        return 2
    configure_logging(settings.log_level)
    log = get_logger(__name__)
    runtime = ProductionRuntime.from_settings(settings, device=args.device)
    app = create_app(runtime, docs_enabled=settings.docs_enabled, debug=settings.debug)
    import uvicorn

    log.info("api starting", extra={"host": args.host, "port": args.port, "device": args.device})
    uvicorn.run(app, host=args.host, port=args.port, log_config=None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
