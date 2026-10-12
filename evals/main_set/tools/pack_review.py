"""Compatibility CLI; implementation: medops.evals.tools.main_set.pack_review."""

import sys

from medops.evals.tools.main_set.pack_review import main

if __name__ == "__main__":
    main(sys.argv[1:] or ["MA", "PV", "CO", "EN", "NA"])
