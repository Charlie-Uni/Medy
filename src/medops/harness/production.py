"""Pinned production model configuration for the harness (ADR-0010 vendor, ADR-0011 judge tier).

These identifiers enter every trace's `VersionSet.model_config_version`; changing one is a policy release
(INV-HAR-05/06), so the values are pinned here and by a unit test, never read from the environment.
"""

from __future__ import annotations

from medops.verification.verifier import DEFAULT_POLICY, VERIFIER_VERSION

PRODUCTION_ANSWER_MODEL = "gpt-6-sol"  # ADR-0010 §4 candidate, confirmed by the live runs of record 54
PRODUCTION_JUDGE_MODEL = "gpt-6-sol"  # ADR-0011 §4: pre-registered rule over the DEC-003 arms (record 53 §4)
PRODUCTION_JUDGE_POLICY = DEFAULT_POLICY


def production_model_config_version() -> str:
    return f"answer={PRODUCTION_ANSWER_MODEL};judge={PRODUCTION_JUDGE_MODEL};{VERIFIER_VERSION}"
