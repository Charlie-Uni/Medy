"""Shared skill judgments test support; no collected test cases."""


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
