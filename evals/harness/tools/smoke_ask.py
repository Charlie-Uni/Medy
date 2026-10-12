"""Compatibility CLI; implementation: medops.evals.tools.harness.smoke_ask."""

import sys

from medops.core.telemetry import flush
from medops.evals.tools.harness.smoke_ask import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        flush()
