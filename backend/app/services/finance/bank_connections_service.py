"""Simplified bank connection status for the Connect banks UI."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FinanceAccountRow, FinanceLiabilityRow
from app.integrations.open_banking.factory import is_connection_linked
from app.schemas.finance import (
    BankConnectionItem,
    BankConnectionMethod,
    BankConnectionStatus,
    FinanceAccountSource,
    OpenBankingRequisition,
)
from app.services.open_banking_settings_service import open_banking_settings_service
from app.services.quickfile_settings_service import quickfile_settings_service


@dataclass(frozen=True)
class TargetBank:
    id: str
    label: str
    method: BankConnectionMethod
    institution_keywords: tuple[str, ...] = ()
    account_keywords: tuple[str, ...] = ()
    account_type: str | None = None


TARGET_BANKS: dict[str, TargetBank] = {
    "lloyds": TargetBank(
        "lloyds",
        "Lloyds",
        BankConnectionMethod.OPEN_BANKING,
        institution_keywords=("lloyds",),
        account_keywords=("lloyds",),
        account_type="current",
    ),
    "mbna": TargetBank(
        "mbna",
        "MBNA",
        BankConnectionMethod.OPEN_BANKING,
        institution_keywords=("mbna",),
        account_keywords=("mbna",),
    ),
    "virgin": TargetBank(
        "virgin",
        "Virgin Money",
        BankConnectionMethod.OPEN_BANKING,
        institution_keywords=("virgin",),
        account_keywords=("virgin",),
    ),
    "capital_on_tap": TargetBank(
        "capital_on_tap",
        "Capital on Tap",
        BankConnectionMethod.QUICKFILE,
        account_keywords=("capital on tap",),
    ),
    "funding_circle": TargetBank(
        "funding_circle",
        "Funding Circle",
        BankConnectionMethod.MANUAL,
        account_keywords=("funding circle",),
    ),
}


def _matches_keywords(text: str, keywords: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _format_sync_time(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return raw


def _find_ob_requisitions(
    bank: TargetBank,
    requisitions: list[OpenBankingRequisition],
    *,
    linked_only: bool,
    config,
) -> list[OpenBankingRequisition]:
    matches: list[OpenBankingRequisition] = []
    for req in requisitions:
        if not _matches_keywords(req.institution_name, bank.institution_keywords):
            continue
        if linked_only and not is_connection_linked(config, req):
            continue
        matches.append(req)
    return matches


async def _matching_accounts(
    db: AsyncSession,
    bank: TargetBank,
) -> list[FinanceAccountRow]:
    rows = await db.scalars(select(FinanceAccountRow).where(FinanceAccountRow.is_active.is_(True)))
    matches: list[FinanceAccountRow] = []
    for row in rows.all():
        haystack = f"{row.name} {row.provider}".lower()
        if bank.account_keywords and not _matches_keywords(haystack, bank.account_keywords):
            continue
        if bank.account_type and row.account_type != bank.account_type:
            continue
        matches.append(row)
    return matches


async def _matching_liabilities(
    db: AsyncSession,
    bank: TargetBank,
) -> list[FinanceLiabilityRow]:
    rows = await db.scalars(
        select(FinanceLiabilityRow).where(FinanceLiabilityRow.is_active.is_(True))
    )
    return [row for row in rows.all() if _matches_keywords(row.name, bank.account_keywords)]


def _sum_balances(accounts: list[FinanceAccountRow], liabilities: list[FinanceLiabilityRow]) -> float:
    total = sum(account.balance_gbp for account in accounts)
    total += sum(liability.balance_gbp for liability in liabilities)
    return round(total, 2)


async def _build_open_banking_connection(
    db: AsyncSession,
    bank: TargetBank,
    *,
    config,
    requisitions: list[OpenBankingRequisition],
    last_sync_at: str | None,
) -> BankConnectionItem:
    if not open_banking_settings_service.is_configured(config):
        return BankConnectionItem(
            id=bank.id,
            label=bank.label,
            method=bank.method,
            status=BankConnectionStatus.NOT_CONFIGURED,
            status_message=(
                "Open Banking is not set up yet. Complete Open Banking Settings once, then return here."
            ),
        )

    linked = _find_ob_requisitions(bank, requisitions, linked_only=True, config=config)
    pending = _find_ob_requisitions(bank, requisitions, linked_only=False, config=config)
    expired = [
        req
        for req in _find_ob_requisitions(bank, requisitions, linked_only=False, config=config)
        if req.status == "EXPIRED"
    ]
    accounts = await _matching_accounts(db, bank)
    ob_accounts = [
        account
        for account in accounts
        if account.source == FinanceAccountSource.OPEN_BANKING.value
    ]
    balance = _sum_balances(ob_accounts, [])
    institution = linked[0].institution_name if linked else (pending[0].institution_name if pending else "")

    if expired and not linked:
        return BankConnectionItem(
            id=bank.id,
            label=bank.label,
            method=bank.method,
            status=BankConnectionStatus.NEEDS_RECONNECTION,
            status_message="Consent expired. Press Connect and sign in at your bank again.",
            last_sync_at=_format_sync_time(last_sync_at),
            institution=expired[0].institution_name,
            account_count=0,
            balance_gbp=0.0,
        )

    if linked:
        if last_sync_at:
            message = f"Connected. Last synced {last_sync_at}."
        else:
            message = "Connected. Use Sync to refresh balances and transactions."
        return BankConnectionItem(
            id=bank.id,
            label=bank.label,
            method=bank.method,
            status=BankConnectionStatus.CONNECTED,
            status_message=message,
            last_sync_at=_format_sync_time(last_sync_at),
            institution=institution,
            account_count=len(ob_accounts),
            balance_gbp=balance,
        )

    if pending:
        return BankConnectionItem(
            id=bank.id,
            label=bank.label,
            method=bank.method,
            status=BankConnectionStatus.AWAITING_LOGIN,
            status_message="Bank login started but not finished. Complete authorisation or try again.",
            institution=institution,
            account_count=0,
            balance_gbp=0.0,
        )

    return BankConnectionItem(
        id=bank.id,
        label=bank.label,
        method=bank.method,
        status=BankConnectionStatus.NOT_CONNECTED,
        status_message="Not connected. Log in via Connect banks to link this account.",
        institution=institution,
        account_count=0,
        balance_gbp=0.0,
    )


async def _build_quickfile_connection(
    db: AsyncSession,
    bank: TargetBank,
    *,
    last_sync_at: str | None,
) -> BankConnectionItem:
    status = await quickfile_settings_service.get_status(db)
    if not status.configured:
        return BankConnectionItem(
            id=bank.id,
            label=bank.label,
            method=bank.method,
            status=BankConnectionStatus.NOT_CONFIGURED,
            status_message="QuickFile is not set up yet. Add API credentials in Settings.",
        )

    accounts = await _matching_accounts(db, bank)
    qf_accounts = [
        account for account in accounts if account.source == FinanceAccountSource.QUICKFILE.value
    ]
    balance = _sum_balances(qf_accounts, [])
    if qf_accounts:
        message = "Synced from QuickFile."
        if last_sync_at:
            message = f"Synced from QuickFile. Last synced {last_sync_at}."
        return BankConnectionItem(
            id=bank.id,
            label=bank.label,
            method=bank.method,
            status=BankConnectionStatus.CONNECTED,
            status_message=message,
            last_sync_at=_format_sync_time(last_sync_at),
            institution="QuickFile",
            account_count=len(qf_accounts),
            balance_gbp=balance,
        )

    return BankConnectionItem(
        id=bank.id,
        label=bank.label,
        method=bank.method,
        status=BankConnectionStatus.NOT_CONNECTED,
        status_message="QuickFile is connected but this account has not synced yet. Run a business sync.",
        institution="QuickFile",
        account_count=0,
        balance_gbp=0.0,
    )


async def _build_manual_connection(db: AsyncSession, bank: TargetBank) -> BankConnectionItem:
    accounts = await _matching_accounts(db, bank)
    liabilities = await _matching_liabilities(db, bank)
    manual_accounts = [
        account
        for account in accounts
        if account.source == FinanceAccountSource.MANUAL.value
    ]
    balance = _sum_balances(manual_accounts, liabilities)
    count = len(manual_accounts) + len(liabilities)

    if count:
        return BankConnectionItem(
            id=bank.id,
            label=bank.label,
            method=bank.method,
            status=BankConnectionStatus.MANUAL,
            status_message="Balance entered manually. Update it when your loan statement changes.",
            institution="Manual",
            account_count=count,
            balance_gbp=balance,
        )

    return BankConnectionItem(
        id=bank.id,
        label=bank.label,
        method=bank.method,
        status=BankConnectionStatus.NOT_CONNECTED,
        status_message="Not added yet. Add Funding Circle as a manual loan on the Connect banks page.",
        institution="Manual",
        account_count=0,
        balance_gbp=0.0,
    )


async def get_connections(db: AsyncSession) -> list[BankConnectionItem]:
    config = await open_banking_settings_service.get_config(db)
    requisitions = await open_banking_settings_service.list_requisitions(db)
    ob_sync_row = await open_banking_settings_service._get_row(db, "open_banking_last_sync_at")
    qf_sync_row = await quickfile_settings_service._get_row(db, "quickfile_last_sync_at")
    ob_last_sync = ob_sync_row.value if ob_sync_row else None
    qf_last_sync = qf_sync_row.value if qf_sync_row else None

    items: list[BankConnectionItem] = []
    for bank in TARGET_BANKS.values():
        if bank.method == BankConnectionMethod.OPEN_BANKING:
            items.append(
                await _build_open_banking_connection(
                    db,
                    bank,
                    config=config,
                    requisitions=requisitions,
                    last_sync_at=ob_last_sync,
                )
            )
        elif bank.method == BankConnectionMethod.QUICKFILE:
            items.append(
                await _build_quickfile_connection(db, bank, last_sync_at=qf_last_sync)
            )
        else:
            items.append(await _build_manual_connection(db, bank))
    return items


async def disconnect(db: AsyncSession, connection_id: str) -> bool:
    bank = TARGET_BANKS.get(connection_id)
    if bank is None:
        return False
    if bank.method != BankConnectionMethod.OPEN_BANKING:
        return False

    config = await open_banking_settings_service.get_config(db)
    requisitions = await open_banking_settings_service.list_requisitions(db)
    remaining = [
        req
        for req in requisitions
        if not _matches_keywords(req.institution_name, bank.institution_keywords)
    ]
    if len(remaining) == len(requisitions):
        return False

    await open_banking_settings_service.save_requisitions(db, remaining)

    now = datetime.now(timezone.utc)
    accounts = await _matching_accounts(db, bank)
    for account in accounts:
        if account.source == FinanceAccountSource.OPEN_BANKING.value:
            account.is_active = False
            account.updated_at = now
    await db.commit()
    return True


async def list_transactions(db: AsyncSession, *, limit: int = 50) -> list:
    from app.db.models import FinanceTransactionRow
    from app.schemas.finance import FinanceTransaction

    rows = await db.scalars(
        select(FinanceTransactionRow)
        .order_by(
            FinanceTransactionRow.transaction_date.desc(),
            FinanceTransactionRow.id.desc(),
        )
        .limit(limit)
    )
    return [
        FinanceTransaction(
            id=row.id,
            account_id=row.account_id,
            external_id=row.external_id,
            transaction_date=row.transaction_date,
            description=row.description,
            merchant=row.merchant,
            amount_gbp=row.amount_gbp,
            category=row.category,
            reference=row.reference,
            is_pending=row.is_pending,
            synced_at=row.synced_at,
            created_at=row.created_at,
        )
        for row in rows.all()
    ]
