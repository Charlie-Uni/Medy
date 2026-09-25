# Backup / restore drill (2026-09-25)

- dump `medops_v2-20260925T135918Z.dump` (66770063 bytes, sha256 463e0d9a2acd709c…), source `medops_v2`, scratch `medops_v2_restore_drill` (dropped afterwards)
- pg_restore rc 0 in 88.3 s; alembic 0019; 34 tables; 63293 rows
- tables match: True; alembic match: True; corpus md5 match: True; grantees match: True; row-count mismatches: none
- **ok: True**
