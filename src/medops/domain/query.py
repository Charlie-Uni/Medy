"""Transport-independent date/archival context (ARCH-02).

Resolve the day once per execution. An explicit date enables archived evidence;
pinning the ordinary clock to the same day does not. Bare document versions have
no unique document/family identity in the Ask/Task contract and are unsupported.
"""

from collections.abc import Mapping
from datetime import date

from medops.core.errors import BusinessError, ErrorCode
from medops.domain.common import DomainModel


class QueryContext(DomainModel):
    as_of: date
    historical_requested: bool = False

    @property
    def selector(self) -> dict[str, str] | None:
        return {"as_of": self.as_of.isoformat()} if self.historical_requested else None


def resolve_query_context(
    historical: Mapping[str, object] | None, *, default_as_of: date | None = None
) -> QueryContext:
    if historical is None:
        return QueryContext(as_of=default_as_of or date.today())
    if not isinstance(historical, Mapping) or set(historical) - {"as_of", "version"}:
        raise BusinessError(ErrorCode.invalid_request, "invalid historical selector")
    version, value = historical.get("version"), historical.get("as_of")
    if (version is None) == (value is None):
        raise BusinessError(ErrorCode.invalid_request, "historical request needs exactly one selector")
    if version is not None:
        raise BusinessError(
            ErrorCode.invalid_request,
            "bare historical version is unsupported without a document identity; use historical.as_of",
        )
    if type(value) is date:
        when = value
    elif isinstance(value, str):
        try:
            when = date.fromisoformat(value)
            if when.isoformat() != value:
                raise ValueError("non-canonical date")
        except ValueError:
            raise BusinessError(ErrorCode.invalid_request, "historical.as_of must be YYYY-MM-DD") from None
    else:
        raise BusinessError(ErrorCode.invalid_request, "historical.as_of must be a date")
    return QueryContext(as_of=when, historical_requested=True)
