"""Compatibility CLI; implementation: medops.evals.tools.harness.perf_run."""

import platform
import re
import sys

from medops.evals.tools.harness.perf_run import main

if __name__ == "__main__":
    if not re.match(r"^3\.1[1-9]", platform.python_version()):
        print("python 3.11+ required", file=sys.stderr)
    sys.exit(main())
