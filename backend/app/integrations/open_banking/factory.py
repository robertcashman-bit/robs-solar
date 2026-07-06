"""Open Banking adapter factory."""

from __future__ import annotations

from app.integrations.open_banking.enable_banking_adapter import EnableBankingAdapter
from app.integrations.open_banking.gocardless_adapter import GoCardlessOpenBankingAdapter
from app.schemas.finance import OpenBankingConfig


def get_open_banking_adapter(config: OpenBankingConfig):
    if config.provider == "gocardless":
        return GoCardlessOpenBankingAdapter(config)
    return EnableBankingAdapter(config)


def is_connection_linked(config: OpenBankingConfig, connection) -> bool:
    return get_open_banking_adapter(config).is_linked(connection)
