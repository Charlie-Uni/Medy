"""Compatibility CLI; implementation: medops.evals.tools.harness.safety_run."""

import sys

from medops.core.telemetry import flush
from medops.evals.tools.harness.safety_run import main

if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        flush()
