"""Model Gateway (baseline 5.7, ADR-0010): the only path from the harness to an LLM.

Harness nodes depend on the `ModelGateway` protocol; adapters live here (OpenAI for the runtime, a fake for
tests). Timeouts, retries, concurrency and budgets are enforced around the gateway, never inside prompts.
"""
