"""Scripted verdicts test plumbing, not the correctness of a real semantic model."""


def supported_reply(*keys: str) -> dict:
    return {
        "checks": [
            {
                "key": key,
                "conclusion": "supported",
                "rationale": "supported",
                "clause_relevance": "supported",
                "observation_grounding": "supported",
            }
            for key in keys
        ]
    }
