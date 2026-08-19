"""Sterling formatting helpers."""

from app.services.finance.money import format_gbp


def test_format_gbp_uses_pound_sign_not_gbp_word() -> None:
    assert format_gbp(10749) == "£10,749.00"
    assert format_gbp(-4452.51) == "-£4,452.51"
    assert format_gbp(13.23, decimals=2) == "£13.23"
    assert "GBP" not in format_gbp(5053)
    assert format_gbp(None) == "—"
