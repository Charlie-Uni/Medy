"""Run only the public synthetic self-check; no arbitrary corpus/path inputs."""

from __future__ import annotations

import argparse
import json

from medops.evals.isolation.canary import self_check
from medops.evals.isolation.contracts import IsolationError


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--self-check", action="store_true", required=True)
    parser.parse_args()
    try:
        result = self_check()
    except IsolationError as error:
        print(json.dumps({"error": error.code}))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
