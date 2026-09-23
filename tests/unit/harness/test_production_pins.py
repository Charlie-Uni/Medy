"""The production model configuration is pinned (INV-HAR-05): a change here is a deliberate policy release."""

from medops.harness.production import (
    PRODUCTION_ANSWER_MODEL,
    PRODUCTION_JUDGE_MODEL,
    PRODUCTION_JUDGE_POLICY,
    production_model_config_version,
)
from medops.infrastructure.llm.gateway import OPENAI_PRICES


def test_production_models_are_pinned_priced_and_versioned():
    assert PRODUCTION_ANSWER_MODEL == "gpt-6-sol"
    assert PRODUCTION_JUDGE_MODEL == "gpt-6-sol"
    assert PRODUCTION_JUDGE_POLICY == "polarity_only"
    assert PRODUCTION_ANSWER_MODEL in OPENAI_PRICES and PRODUCTION_JUDGE_MODEL in OPENAI_PRICES
    assert (
        production_model_config_version()
        == "answer=gpt-6-sol;judge=gpt-6-sol;verifier-v2+support-rules-v1+polarity_only"
    )
