from app.schemas.finance import FinanceAccountSource


def test_legacy_lunch_flow_source_maps_to_lunchflow() -> None:
    assert FinanceAccountSource("lunch_flow") is FinanceAccountSource.LUNCHFLOW
    assert FinanceAccountSource("lunchflow") is FinanceAccountSource.LUNCHFLOW
