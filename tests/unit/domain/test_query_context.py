"""Strict selector semantics independent of the HTTP and task transports."""

from datetime import date, datetime

import pytest

from medops.core.errors import BusinessError, ErrorCode
from medops.domain.query import QueryContext, resolve_query_context


def test_same_day_does_not_make_an_ordinary_request_historical():
    when = date(2025, 1, 1)
    normal = resolve_query_context(None, default_as_of=when)
    historical = resolve_query_context({"as_of": "2025-01-01", "version": None}, default_as_of=date(2026, 10, 11))
    assert normal.as_of == historical.as_of == when
    assert normal.historical_requested is False and normal.selector is None
    assert historical.historical_requested is True and historical.selector == {"as_of": "2025-01-01"}
    assert QueryContext.model_validate_json(historical.model_dump_json()) == historical


@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"version": "v1"},
        {"version": "2025-01-01"},
        {"version": "v1", "as_of": "2025-01-01"},
        {"as_of": "2025-02-30"},
        {"as_of": "20250101"},
        {"as_of": "2025-W01-3"},
        {"as_of": 20250101},
        {"as_of": datetime(2025, 1, 1)},
        {"as_of": "2025-01-01", "document": "d"},
    ],
)
def test_unsupported_and_malformed_selectors_are_never_defaulted_to_today(raw):
    with pytest.raises(BusinessError) as exc:
        resolve_query_context(raw)
    assert exc.value.code is ErrorCode.invalid_request


def test_an_internal_date_is_accepted_without_string_roundtrip():
    assert resolve_query_context({"as_of": date(2025, 1, 1)}).as_of == date(2025, 1, 1)
