"""Conservative USD conversion for integer execution-accounting snapshots."""

from decimal import ROUND_CEILING, Decimal


def usd_to_microusd(cost: float) -> int:
    return int((Decimal(str(cost)) * 1_000_000).to_integral_value(rounding=ROUND_CEILING))
