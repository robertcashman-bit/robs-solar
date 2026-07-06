"""Asset and liability breakdown for net worth and overview tiles."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.finance import (
    DebtType,
    FinanceAccount,
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


def _sum_liabilities(
    liabilities: list[FinanceLiability],
    *,
    scope: FinanceScope | None = None,
    debt_types: set[DebtType] | None = None,
) -> float:
    total = 0.0
    for liability in liabilities:
        if scope is not None and liability.scope != scope:
            continue
        if debt_types is not None and liability.debt_type not in debt_types:
            continue
        total += liability.balance_gbp
    return total


def build_balance_breakdown(
    accounts: list[FinanceAccount],
    liabilities: list[FinanceLiability],
    *,
    debtors_gbp: float = 0.0,
) -> FinanceBalanceBreakdown:
    personal_current = _sum_accounts(
        accounts,
        scope=FinanceScope.PERSONAL,
        account_types={FinanceAccountType.CURRENT},
    )
    business_current = _sum_accounts(
        accounts,
        scope=FinanceScope.BUSINESS,
        account_types={FinanceAccountType.CURRENT},
    )
    personal_liquid = max(0.0, personal_current)
    business_liquid = max(0.0, business_current)
    business_overdraft = abs(min(0.0, business_current))

    vat_reserve = _sum_accounts(accounts, account_types={FinanceAccountType.VAT_RESERVE})
    corp_tax_reserve = _sum_accounts(accounts, account_types={FinanceAccountType.CORP_TAX_RESERVE})
    pension = _sum_accounts(accounts, account_types={FinanceAccountType.PENSION})
    property_value = _sum_accounts(accounts, account_types={FinanceAccountType.PROPERTY})
    debtors = debtors_gbp or _sum_accounts(accounts, account_types={FinanceAccountType.DEBTORS})

    liquid_assets = personal_liquid + business_liquid + vat_reserve + corp_tax_reserve
    long_term_assets = property_value + pension + debtors
    total_assets = liquid_assets + long_term_assets

    personal_short = _sum_liabilities(
        liabilities,
        scope=FinanceScope.PERSONAL,
        debt_types=SHORT_TERM_DEBT_TYPES,
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
        + business_overdraft
    )
    business_long = _sum_debt_accounts(
        accounts,
        scope=FinanceScope.BUSINESS,
        account_types=LONG_TERM_BUSINESS_ACCOUNT_TYPES,
    )
    business_total_debt = business_short + business_long

    credit_cards = _sum_liabilities(
        liabilities,
        scope=FinanceScope.PERSONAL,
        debt_types={DebtType.CREDIT_CARD},
    ) + _sum_debt_accounts(
        accounts,
        scope=FinanceScope.BUSINESS,
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
