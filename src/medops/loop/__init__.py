"""The controlled self-evolution Loop (baseline 5.8, M4): Observe -> Reflect -> Adapt -> Replay -> Approve -> Canary.

Everything here runs on the Loop database role, which reads signals and writes candidates and cases only; released
policy is never written from this package (INV-AUTH-05)."""
