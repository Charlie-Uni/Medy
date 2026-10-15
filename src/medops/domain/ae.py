"""Shared adverse-event vocabulary; descriptive extraction fields, never case-validity rules."""

from typing import Literal

AeKind = Literal[
    "patient",
    "suspect_drug",
    "concomitant_drug",
    "event",
    "onset",
    "seriousness",
    "outcome",
    "dechallenge_rechallenge",
    "reporter",
]
KINDS: tuple[AeKind, ...] = (
    "patient",
    "suspect_drug",
    "concomitant_drug",
    "event",
    "onset",
    "seriousness",
    "outcome",
    "dechallenge_rechallenge",
    "reporter",
)
