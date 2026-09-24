"""Write the safety-set draft files from the authoring modules (spec-s1 §6 step 1).

python evals/safety_set/tools/author_drafts.py [--only A,B1,...]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import DRAFT_FILES, DRAFTS, write_jsonl  # noqa: E402

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
