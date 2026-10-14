"""Run only the public synthetic self-check; no arbitrary corpus/path inputs."""

from __future__ import annotations

import argparse
import json

from medops.evals.isolation.canary import export_self_check, self_check
from medops.evals.isolation.contracts import IsolationError
from medops.evals.isolation.screening_canary import screening_self_check


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    checks = parser.add_mutually_exclusive_group(required=True)
    checks.add_argument("--self-check", action="store_true")
    checks.add_argument("--export-self-check", action="store_true")
    checks.add_argument("--screening-self-check", action="store_true")
    args = parser.parse_args()
    try:
        if args.screening_self_check:
            result = screening_self_check()
        else:
            result = export_self_check() if args.export_self_check else self_check()
    except IsolationError as error:
        print(json.dumps({"error": error.code}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
