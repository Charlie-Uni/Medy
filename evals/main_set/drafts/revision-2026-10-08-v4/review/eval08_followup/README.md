# EVAL-08 v4 follow-up review

Only `ms-0241` and `ms-0242` are present. Each call uses one sample. Authorization caps this package at two attempts and 0.50 USD total, stops after any nonvalidated attempt, and permits no automatic retry.

Completed attempts: `ms-0241` returned agree at ledger cost 0.190079 USD. `ms-0242` returned `error_max_budget_usd` without a verdict at ledger cost 0.251998 USD; the reported 0.2519975 USD exceeded the 0.25 per-call reservation and was flagged. Total ledger cost is 0.442077 USD. No retry was attempted.
