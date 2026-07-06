"""Unit tests for Open Banking adapter factory."""

from app.integrations.open_banking.enable_banking_adapter import EnableBankingAdapter
from app.integrations.open_banking.factory import get_open_banking_adapter
from app.integrations.open_banking.gocardless_adapter import GoCardlessOpenBankingAdapter
from app.schemas.finance import OpenBankingConfig, OpenBankingRequisition


def test_factory_defaults_to_enable() -> None:
    adapter = get_open_banking_adapter(OpenBankingConfig())
    assert isinstance(adapter, EnableBankingAdapter)


def test_factory_gocardless_legacy() -> None:
    adapter = get_open_banking_adapter(
        OpenBankingConfig(provider="gocardless", secret_id="a", secret_key="b")
    )
    assert isinstance(adapter, GoCardlessOpenBankingAdapter)


def test_enable_linked_status() -> None:
    adapter = EnableBankingAdapter(OpenBankingConfig())
    pending = OpenBankingRequisition(
        id="1",
        institution_id="GB:Mock",
        institution_name="Mock",
        status="CR",
    )
    assert not adapter.is_linked(pending)
    linked = OpenBankingRequisition(
        id="sess",
        institution_id="GB:Mock",
        institution_name="Mock",
        status="AUTHORIZED",
        account_ids=["acc-1"],
    )
    assert adapter.is_linked(linked)


def test_gocardless_linked_status() -> None:
    adapter = GoCardlessOpenBankingAdapter(
        OpenBankingConfig(provider="gocardless", secret_id="a", secret_key="b")
    )
    assert not adapter.is_linked(
        OpenBankingRequisition(id="1", institution_id="X", institution_name="X", status="CR")
    )
    assert adapter.is_linked(
        OpenBankingRequisition(
            id="1",
            institution_id="X",
            institution_name="X",
            status="LN",
            account_ids=["acc"],
            provider="gocardless",
        )
    )
