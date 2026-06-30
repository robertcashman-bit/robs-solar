"""Unit tests for the sell-to-grid advisor logic."""

from app.services.sell_advisor_service import evaluate_sell_opportunity

CAPACITY = 16.0


def _evaluate(*, soc, export, threshold=0.15, min_soc=50, configured=True, imp=0.28):
    return evaluate_sell_opportunity(
        battery_soc_pct=soc,
        export_rate_gbp=export,
        import_rate_gbp=imp,
        threshold_gbp=threshold,
        min_soc_pct=min_soc,
        capacity_kwh=CAPACITY,
        configured=configured,
    )


def test_worth_selling_when_price_high_and_headroom() -> None:
    op = _evaluate(soc=90, export=0.20)
    assert op.worth_selling is True
    # 40% of 16 kWh headroom = 6.4 kWh
    assert op.sellable_kwh == 6.4
    assert op.estimated_value_gbp == round(6.4 * 0.20, 2)
    assert "worth selling" in op.headline.lower()


def test_not_worth_when_price_below_threshold() -> None:
    op = _evaluate(soc=90, export=0.10)
    assert op.worth_selling is False
    assert "not worth" in op.headline.lower()


def test_good_price_but_low_battery() -> None:
    op = _evaluate(soc=45, export=0.25, min_soc=50)
    assert op.worth_selling is False
    assert op.sellable_kwh == 0.0
    assert "reserve" in op.headline.lower()


def test_not_configured() -> None:
    op = _evaluate(soc=90, export=None, configured=False)
    assert op.worth_selling is False
    assert op.configured is False
    assert "octopus" in op.message.lower()


def test_export_pence_rounding() -> None:
    op = _evaluate(soc=80, export=0.1567)
    assert op.export_rate_pence == 15.7
    assert op.threshold_pence == 15.0
