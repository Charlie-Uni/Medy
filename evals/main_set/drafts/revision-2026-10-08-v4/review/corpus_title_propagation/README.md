# Corpus title propagation review

The confirmed correction of the FDA guidance title from September 2021 to December 2025 changes the byte-level reviewer input for seven otherwise unchanged samples. This package re-reviews exactly those inputs before `main-v4-provisional` assembly.

- Samples: `ms-0235`, `ms-0236`, `ms-0237`, `ms-0238`, `ms-0239`, `ms-0240`, `ms-0475`.
- Calls: at most seven, one sample per call.
- Model: `claude-opus-5`, requested effort `high`.
- Budget: 2.25 USD total authorization; 0.30 USD CLI threshold per call; no automatic retry.
- This is an independent LLM review. It does not count as the missing second independent human review.
