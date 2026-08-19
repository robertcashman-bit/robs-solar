"""Penny-accurate sterling helpers. Never invent a figure."""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation

TWOPLACE = Decimal("0.01")
PENCE = Decimal("1")


def to_decimal(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def to_pence(value: object) -> int | None:
    amount = to_decimal(value)
    if amount is None:
        return None
    return int((amount * 100).quantize(PENCE, rounding=ROUND_HALF_EVEN))


def from_pence(pence: int | None) -> float:
    if pence is None:
        return 0.0
    return float((Decimal(pence) / 100).quantize(TWOPLACE, rounding=ROUND_HALF_EVEN))


def quantize_gbp(value: object) -> float | None:
    amount = to_decimal(value)
    if amount is None:
        return None
    return float(amount.quantize(TWOPLACE, rounding=ROUND_HALF_EVEN))


def format_gbp(value: object, *, decimals: int = 2) -> str:
    """User-facing sterling — prefer £ over the word GBP."""
    amount = quantize_gbp(value)
    if amount is None:
        return "—"
    quantized = Decimal(str(amount)).quantize(
        Decimal("0.01") if decimals == 2 else Decimal(10) ** -decimals,
        rounding=ROUND_HALF_EVEN,
    )
    sign = "-" if quantized < 0 else ""
    body = f"{abs(quantized):,.{decimals}f}"
    return f"{sign}£{body}"
