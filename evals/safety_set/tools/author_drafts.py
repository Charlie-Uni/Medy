"""Write the safety-set draft files from the authoring modules (spec-s1 §6 step 1).

python evals/safety_set/tools/author_drafts.py [--only A,B1,...]

Re-running is safe for reviewed rows (record 114): a row whose content is unchanged keeps the `review` block the
independent reviewer wrote into the draft file; a new or changed row starts as `pending`. Ids a module lists in
`WITHDRAWN` are moved verbatim (review included) to drafts/withdrawn/<same file>, never deleted, and
drafts/withdrawn/manifest.json says what replaced them and why.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import DRAFT_FILES, DRAFTS, WITHDRAWN, read_jsonl, write_jsonl  # noqa: E402

MODULES = {
    "A": ("high_risk", "authoring.a_high_risk"),
    "B1": ("injection_input", "authoring.b1_injection_input"),
    "B2": ("injection_document", "authoring.b2_injection_document"),
    "C1": ("acl_cross_dept", "authoring.c1_acl_cross_dept"),
    "C2": ("acl_skill_scope", "authoring.c2_acl_skill_scope"),
    "D1": ("ungrounded", "authoring.d1_ungrounded"),
    "D2": ("numeric_trap", "authoring.d2_numeric_trap"),
    "E": ("combined", "authoring.e_combined"),
    "F": ("version_guard", "authoring.f_version_guard"),
}


CONTENT_KEYS_IGNORED = {"review", "dataset_version"}  # a review binds to the sample's content, not to these


def content(row: dict) -> dict:
    return {k: v for k, v in row.items() if k not in CONTENT_KEYS_IGNORED}


def merge_reviews(new_rows: list[dict], existing: list[dict]) -> list[dict]:
    """New rows with the stored review carried over wherever the sample content is identical."""
    stored = {r["sample_id"]: r for r in existing}
    out = []
    for row in new_rows:
        old = stored.get(row["sample_id"])
        if old is not None and content(old) == content(row) and "review" in old:
            row = {**row, "review": old["review"]}
        out.append(row)
    return out


def split_withdrawn(existing: list[dict], withdrawn: dict[str, tuple[str, str]], already: list[dict]) -> list[dict]:
    """The withdrawn file's rows: what it already holds plus the existing rows of the ids withdrawn now, verbatim."""
    held = {r["sample_id"]: r for r in already}
    for r in existing:
        if r["sample_id"] in withdrawn and r["sample_id"] not in held:
            held[r["sample_id"]] = r
    return [held[k] for k in sorted(held)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    args = ap.parse_args()
    wanted = {x.strip() for x in args.only.split(",") if x.strip()} or set(MODULES)
    DRAFTS.mkdir(parents=True, exist_ok=True)
    provenance = {}
    for code, (category, module_name) in MODULES.items():
        if code not in wanted:
            continue
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                print(f"{code}: module {module_name} not written yet")
                continue
            raise  # a broken import inside an authoring module must not silently keep stale drafts
        rows = module.rows()
        bad = [r["sample_id"] for r in rows if r["category"] != category]
        if bad:
            raise SystemExit(f"{code}: wrong category on {bad}")
        path = DRAFTS / DRAFT_FILES[category]
        existing = read_jsonl(path)
        withdrawn: dict[str, tuple[str, str]] = getattr(module, "WITHDRAWN", {})
        still_active = [r["sample_id"] for r in rows if r["sample_id"] in withdrawn]
        if still_active:
            raise SystemExit(f"{code}: withdrawn ids still in rows(): {still_active}")
        if withdrawn:
            WITHDRAWN.mkdir(parents=True, exist_ok=True)
            wpath = WITHDRAWN / DRAFT_FILES[category]
            write_jsonl(wpath, split_withdrawn(existing, withdrawn, read_jsonl(wpath)))
            mpath = WITHDRAWN / "manifest.json"
            manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
            for sid, (replaced_by, why) in withdrawn.items():
                manifest.setdefault(sid, {"replaced_by": replaced_by, "reason": why, "category": category})
            mpath.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8"
            )
        rows = merge_reviews(rows, existing)
        write_jsonl(path, rows)
        src = pathlib.Path(module.__file__).read_bytes()
        provenance[category] = {"module": module_name, "sha256": hashlib.sha256(src).hexdigest(), "count": len(rows)}
        print(f"{code}: {len(rows)} rows -> {path.name}")
    prov_path = DRAFTS / "drafting_provenance.json"
    existing = json.loads(prov_path.read_text()) if prov_path.exists() else {}
    existing.update(provenance)
    prov_path.write_text(json.dumps(existing, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
