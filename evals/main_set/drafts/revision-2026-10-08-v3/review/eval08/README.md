# EVAL-08 targeted adjudication review

Only `ms-0241`, `ms-0242`, and `ms-0280` are present. Each call uses one sample. The machine-enforced authorization caps this package at three attempts and 0.75 USD total, and blocks all later calls after any nonvalidated attempt. No automatic retry is authorized.

Completed 2026-10-08: three validated attempts, no failures/retries/unknown charges, ledger cost 0.555900 USD. `ms-0242` and `ms-0280` agreed; `ms-0241` disputed `key_text`. The attempt limit is exhausted, so the displayed 0.194100 USD remainder cannot fund another call under this authorization.
