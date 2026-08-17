"""Legacy Neon rows used source=lunchflow."""

from __future__ import annotations

from app.schemas.finance import FinanceAccountSource
from app.services.finance.finance_accounts_service import _normalize_source


def test_normalize_legacy_lunchflow_source() -> None:
    assert _normalize_source("lunchflow") == FinanceAccountSource.LUNCH_FLOW
    assert _normalize_source("lunch_flow") == FinanceAccountSource.LUNCH_FLOW
