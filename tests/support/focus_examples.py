"""Shared focus examples test support; no collected test cases."""

from __future__ import annotations

from medops.retrieval.rerank import OverlapReranker

SCORER = OverlapReranker().score


DOSE = (
    "本品用於成人高血壓之治療。年齡 6 至 12 歲的孩童：口服，100 mg，一天三次；或 300 mg 當作一個單一劑量，一天一次。"
    "腎功能不全者應依肌酸酐清除率調整劑量。本品應置於兒童伸手不及之處。儲存於攝氏 25 度以下，避免陽光直射及潮濕。"
    "使用前請詳閱說明書，如有疑問請洽詢醫師或藥師。"
)


ENGLISH = (
    "The sponsor should notify the regulatory authority of fatal or life-threatening unexpected adverse reactions "
    "as soon as possible, but no later than 7 calendar days after first knowledge, e.g. by telephone. "
    "A complete report should follow within 8 additional calendar days. The dose was 0.05 mg/kg in study No. 12. "
    "Other serious unexpected reactions should be reported no later than 15 calendar days."
)
