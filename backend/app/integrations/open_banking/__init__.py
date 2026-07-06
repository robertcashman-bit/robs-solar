"""Open Banking provider adapters."""

from app.integrations.open_banking.factory import get_open_banking_adapter

__all__ = ["get_open_banking_adapter"]
