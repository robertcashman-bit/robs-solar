"""Asset and liability breakdown for net worth and overview tiles."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.finance import (
    DebtType,
    FinanceAccount,
    FinanceAccountSource,
    FinanceAccountType,
    FinanceLiability,
    FinanceScope,
)

SHORT_TERM_DEBT_TYPES = {
    DebtType.CREDIT_CARD,
    DebtType.LOAN,
}
LONG_TERM_DEBT_TYPES = {
    DebtType.MORTGAGE,
    DebtType.DIRECTORS_LOAN,
    DebtType.BUSINESS_LOAN,
}

SHORT_TERM_BUSINESS_ACCOUNT_TYPES = {
    FinanceAccountType.CREDIT_CARD,
    FinanceAccountType.CAPITAL_ON_TAP,
    FinanceAccountType.CREDITORS,
}
LONG_TERM_BUSINESS_ACCOUNT_TYPES = {
    FinanceAccountType.DIRECTORS_LOAN,
    FinanceAccountType.LOAN,
}
DEBT_ACCOUNT_TYPES = SHORT_TERM_BUSINESS_ACCOUNT_TYPES | LONG_TERM_BUSINESS_ACCOUNT_TYPES

LIQUID_ACCOUNT_TYPES = {
    FinanceAccountType.CURRENT,
    FinanceAccountType.SAVINGS,
}

_SANDBOX_PROVIDER_MARKERS = ("mock aspsp", "mock aspsp", "sandbox")


def _is_sandbox_account(account: FinanceAccount) -> bool:
    provider = (account.provider or "").strip().lower()
    name = (account.name or "").strip().lower()
    if "mock aspsp" in provider or "mock aspsp" in name:
        return True
    if account.source == FinanceAccountSource.OPEN_BANKING and "sandbox" in provider:
        return True
    return False


def _usable_accounts(accounts: list[FinanceAccount]) -> list[FinanceAccount]:
    return [a for a in accounts if not _is_sandbox_account(account=a)]


def _debt_balance(amount: float) -> float:
    return round(abs(amount), 2)


def _sum_debt_accounts(
    accounts: list[FinanceAccount],
    *,
    scope: FinanceScope | None = None,
    account_types: set[FinanceAccountType] | None = None,
) -> float:
    total = 0.0
    for account in accounts:
        if scope is not None and account.scope != scope:
            continue
        if account_types is not None and account.account_type not in account_types:
            continue
        total += _debt_balance(account.balance_gbp)
    return total


@dataclass(frozen=True)
class FinanceBalanceBreakdown:
    liquid_assets_gbp: float
    long_term_assets_gbp: float
    property_value_gbp: float
    pension_value_gbp: float
    debtors_gbp: float
    total_assets_gbp: float
    short_term_debt_gbp: float
    long_term_debt_gbp: float
    total_debt_gbp: float
    home_equity_gbp: float
    net_worth_estimate_gbp: float
    personal_short_term_debt_gbp: float
    personal_long_term_debt_gbp: float
    personal_total_debt_gbp: float
    business_short_term_debt_gbp: float
    business_long_term_debt_gbp: float
    business_total_debt_gbp: float
    credit_card_balances_gbp: float
    loan_balances_gbp: float
    mortgage_balance_gbp: float
    directors_loan_gbp: float


def _sum_accounts(
    accounts: list[FinanceAccount],
    *,
    scope: FinanceScope | None = None,
    account_types: set[FinanceAccountType] | None = None,
) -> float:
    total = 0.0
    for account in accounts:
        if scope is not None and account.scope != scope:
            continue
        if account_types is not None and account.account_type not in account_types:
            continue
        total += account.balance_gbp
    return total


def _liquid_and_overdraft(
    accounts: list[FinanceAccount],
    *,
    scope: FinanceScope,
) -> tuple[float, float]:
    """Per-account liquid (positive) and overdraft (positive debt), never netting siblings."""
    liquid = 0.0
    overdraft = 0.0
    for account in accounts:
        if account.scope != scope:
            continue
        if account.account_type not in LIQUID_ACCOUNT_TYPES:
            continue
        if account.balance_gbp >= 0:
            liquid += account.balance_gbp
        else:
            overdraft += abs(account.balance_gbp)
    return liquid, overdraft


def _sum_liabilities(
    liabilities: list[FinanceLiability],
    *,
    scope: FinanceScope | None = None,
    debt_types: set[DebtType] | None = None,
    exclude_account_ids: set[int] | None = None,
) -> float:
    total = 0.0
    for liability in liabilities:
        if scope is not None and liability.scope != scope:
            continue
        if debt_types is not None and liability.debt_type not in debt_types:
            continue
        if exclude_account_ids and liability.account_id in exclude_account_ids:
            continue
        total += liability.balance_gbp
    return total


def build_balance_breakdown(
    accounts: list[FinanceAccount],
    liabilities: list[FinanceLiability],
    *,
    debtors_gbp: float | None = None,
) -> FinanceBalanceBreakdown:
    accounts = _usable_accounts(accounts)

    personal_liquid, personal_overdraft = _liquid_and_overdraft(
        accounts, scope=FinanceScope.PERSONAL
    )
    business_liquid, business_overdraft = _liquid_and_overdraft(
        accounts, scope=FinanceScope.BUSINESS
    )

    vat_reserve = _sum_accounts(accounts, account_types={FinanceAccountType.VAT_RESERVE})
    corp_tax_reserve = _sum_accounts(accounts, account_types={FinanceAccountType.CORP_TAX_RESERVE})
    pension = _sum_accounts(accounts, account_types={FinanceAccountType.PENSION})
    property_value = _sum_accounts(accounts, account_types={FinanceAccountType.PROPERTY})
    debtors = (
        debtors_gbp
        if debtors_gbp is not None
        else _sum_accounts(accounts, account_types={FinanceAccountType.DEBTORS})
    )

    liquid_assets = personal_liquid + business_liquid + vat_reserve + corp_tax_reserve
    long_term_assets = property_value + pension + debtors
    total_assets = liquid_assets + long_term_assets

    debt_account_ids = {
        a.id for a in accounts if a.account_type in DEBT_ACCOUNT_TYPES and a.id is not None
    }

    personal_short = (
        _sum_liabilities(
            liabilities,
            scope=FinanceScope.PERSONAL,
            debt_types=SHORT_TERM_DEBT_TYPES,
        )
        + personal_overdraft
    )
    personal_long = _sum_liabilities(
        liabilities,
        scope=FinanceScope.PERSONAL,
        debt_types=LONG_TERM_DEBT_TYPES,
    )
    personal_total_debt = personal_short + personal_long

    business_short = (
        _sum_debt_accounts(
            accounts,
            scope=FinanceScope.BUSINESS,
            account_types=SHORT_TERM_BUSINESS_ACCOUNT_TYPES,
        )
        + _sum_liabilities(
            liabilities,
            scope=FinanceScope.BUSINESS,
            debt_types={DebtType.CREDIT_CARD, DebtType.LOAN},
            exclude_account_ids=debt_account_ids,
        )
        + business_overdraft
    )
    business_long = _sum_debt_accounts(
        accounts,
        scope=FinanceScope.BUSINESS,
        account_types=LONG_TERM_BUSINESS_ACCOUNT_TYPES,
    ) + _sum_liabilities(
        liabilities,
        scope=FinanceScope.BUSINESS,
        debt_types={DebtType.MORTGAGE, DebtType.DIRECTORS_LOAN, DebtType.BUSINESS_LOAN},
        exclude_account_ids=debt_account_ids,
    )
    business_total_debt = business_short + business_long

    credit_cards = _sum_liabilities(
        liabilities,
        debt_types={DebtType.CREDIT_CARD},
        exclude_account_ids=debt_account_ids,
    ) + _sum_debt_accounts(
        accounts,
        account_types={FinanceAccountType.CREDIT_CARD, FinanceAccountType.CAPITAL_ON_TAP},
    )

    personal_loans = _sum_liabilities(
        liabilities,
        scope=FinanceScope.PERSONAL,
        debt_types={DebtType.LOAN},
    )
    business_loans = _sum_debt_accounts(
        accounts,
        scope=FinanceScope.BUSINESS,
        account_types={FinanceAccountType.LOAN},
    ) + _sum_liabilities(
        liabilities,
        scope=FinanceScope.BUSINESS,
        debt_types={DebtType.LOAN, DebtType.BUSINESS_LOAN},
        exclude_account_ids=debt_account_ids,
    )
    loan_balances = personal_loans + business_loans

    mortgage = _sum_liabilities(
        liabilities,
        scope=FinanceScope.PERSONAL,
        debt_types={DebtType.MORTGAGE},
    )

    directors_loan = _sum_debt_accounts(
        accounts,
        scope=FinanceScope.BUSINESS,
        account_types={FinanceAccountType.DIRECTORS_LOAN},
    ) + _sum_liabilities(
        liabilities,
        scope=FinanceScope.BUSINESS,
        debt_types={DebtType.DIRECTORS_LOAN},
        exclude_account_ids=debt_account_ids,
    )

    short_term_debt = personal_short + business_short
    long_term_debt = personal_long + business_long
    total_debt = short_term_debt + long_term_debt
    home_equity = property_value - mortgage
    net_worth = total_assets - total_debt

    return FinanceBalanceBreakdown(
        liquid_assets_gbp=round(liquid_assets, 2),
        long_term_assets_gbp=round(long_term_assets, 2),
        property_value_gbp=round(property_value, 2),
        pension_value_gbp=round(pension, 2),
        debtors_gbp=round(debtors, 2),
        total_assets_gbp=round(total_assets, 2),
        short_term_debt_gbp=round(short_term_debt, 2),
        long_term_debt_gbp=round(long_term_debt, 2),
        total_debt_gbp=round(total_debt, 2),
        home_equity_gbp=round(home_equity, 2),
        net_worth_estimate_gbp=round(net_worth, 2),
        personal_short_term_debt_gbp=round(personal_short, 2),
        personal_long_term_debt_gbp=round(personal_long, 2),
        personal_total_debt_gbp=round(personal_total_debt, 2),
        business_short_term_debt_gbp=round(business_short, 2),
        business_long_term_debt_gbp=round(business_long, 2),
        business_total_debt_gbp=round(business_total_debt, 2),
        credit_card_balances_gbp=round(credit_cards, 2),
        loan_balances_gbp=round(loan_balances, 2),
        mortgage_balance_gbp=round(mortgage, 2),
        directors_loan_gbp=round(directors_loan, 2),
    )
