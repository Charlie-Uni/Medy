"""Pure helpers of the candidate compiler (record 89): the restriction scan must flag document markers, not the
ordinary regulatory use of the same words, and the version / notice extractors must read what the PDFs print."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_PATH = Path(__file__).resolve().parents[3] / "evals/main_set/tools/compile_candidates.py"
_SPEC = importlib.util.spec_from_file_location("compile_candidates", _PATH)
cc = importlib.util.module_from_spec(_SPEC)
sys.modules["compile_candidates"] = cc
_SPEC.loader.exec_module(cc)


def names(text: str) -> set[str]:
    return {n for n, _ in cc.scan_restrictions(text)}


def test_ordinary_use_of_confidential_is_not_a_restriction():
    assert names("the need to protect passwords and to keep them confidential at all times") == set()
    assert names("patient labeling that is not for distribution to patients") == set()


def test_document_markers_are_restrictions():
    assert "confidential" in names("Protocol v3.0 CONFIDENTIAL Do not copy")
    assert "confidential" in names("This document is strictly confidential.")
    assert "not for distribution" in names("Draft – not for distribution.")
    assert "all rights reserved" in names("© 2016 ISO and HL7 International. ALL RIGHTS RESERVED")
    assert names("本仿單版權所有，未經同意不得轉載") >= {"版權所有", "未經同意不得"}


def test_hard_and_soft_split():
    hits = names("© European Medicines Agency, 2017. Reproduction is authorised provided the source is acknowledged.")
    assert hits == {"©"} and not (hits & cc.HARD_RESTRICTIONS)


def test_ema_cover_and_version_extraction():
    head = (
        "9 October 2017 EMA/813938/2011 Rev 3 Guideline on good pharmacovigilance practices (GVP) Module VIII "
        "© European Medicines Agency and Heads of Medicines Agencies, 2017. Reproduction is authorised provided the source is acknowledged."
    )
    assert cc.ema_version(head) == "EMA/813938/2011 Rev 3 (9 October 2017)"
    assert cc.ema_cover_quote(head).startswith("© European Medicines Agency and Heads")


def test_ich_notice_and_date():
    head = (
        "Current Step 4 version dated 26 August 2022 Legal notice: This document is protected by copyright and may, with the "
        "exception of the ICH logo, be used under a public license provided that ICH's copyright in the document is "
        "acknowledged at all times. The above-mentioned permissions do not apply to content supplied by third parties. "
        "Therefore, for documents where the copyright vests in a third party, permission for reproduction must be obtained from this copyright holder."
    )
    assert cc.ich_dated(head) == "26 August 2022"
    assert cc.ich_notice_quote(head).startswith("This document is protected by copyright")


def test_taiwan_dates_and_label_version_line():
    assert cc.tw_date("中華民國 114 年 12 月") == "2025-12"
    assert cc.tw_date("109年8月28日修正") == "2020-08-28"
    assert cc.label_version({"tail": "版本：CCDS 07Apr2020_v2101", "head": ""}).startswith("文内版本行：版本：CCDS")
    assert cc.label_version({"tail": "Each tablet contains 25 mg", "head": ""}) == "仿單正文未见版本行"
