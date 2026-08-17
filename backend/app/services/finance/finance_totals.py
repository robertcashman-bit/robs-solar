"""Shared finance totals used by overview and reports.

Canonical rules (from the existing account + liability model):

* Personal/business bank tiles sum ``current`` accounts only.
* Scope debt tiles (``total_personal_debt`` / ``total_business_debt``) sum
  the liability register for that scope.
* Category tiles (credit cards, loans, mortgage, director's loan) sum
  matching account balances plus liabilities of that type that are not
  already linked to one of those accounts via ``account_id``.
* Net-worth debts are liability balances plus debt-type account balances,
  counting a linked liability only once.
"""

from __future__ import annotations

from app.schemas.finance import FinanceAccount, FinanceAccountType, FinanceLiability, FinanceScope

DEBT_ACCOUNT_TYPES = frozenset(
    {
        FinanceAccountType.CREDIT_CARD,
        FinanceAccountType.LOAN,
        FinanceAccountType.MORTGAGE,
        FinanceAccountType.DIRECTORS_LOAN,
    }
)

CREDIT_CARD_LIABILITY_TYPES = frozenset({"credit_card"})
LOAN_LIABILITY_TYPES = frozenset({"loan", "business_loan"})
MORTGAGE_LIABILITY_TYPES = frozenset({"mortgage"})
DIRECTORS_LOAN_LIABILITY_TYPES = frozenset({"directors_loan"})


def sum_accounts_of_type(accounts: list[FinanceAccount], account_type: FinanceAccountType) -> float:
    return sum(account.balance_gbp for account in accounts if account.account_type == account_type)


def sum_scope_debt(liabilities: list[FinanceLiability], scope: FinanceScope) -> float:
    return sum(debt.balance_gbp for debt in liabilities if debt.scope == scope)


def _linked_account_ids(
    accounts: list[FinanceAccount], account_types: frozenset[FinanceAccountType]
) -> set[int]:
    return {account.id for account in accounts if account.account_type in account_types}


def sum_unlinked_liabilities(
    liabilities: list[FinanceLiability],
    *,
    types: frozenset[str] | None = None,
    exclude_account_ids: set[int] | None = None,
) -> float:
    total = 0.0
    excluded = exclude_account_ids or set()
    for debt in liabilities:
        if types is not None and debt.debt_type.value not in types:
            continue
        if debt.account_id is not None and debt.account_id in excluded:
            continue
        total += debt.balance_gbp
    return total


def category_total(
    accounts: list[FinanceAccount],
    liabilities: list[FinanceLiability],
    account_type: FinanceAccountType,
    liability_types: frozenset[str],
) -> float:
    linked = _linked_account_ids(accounts, frozenset({account_type}))
    return sum_accounts_of_type(accounts, account_type) + sum_unlinked_liabilities(
        liabilities, types=liability_types, exclude_account_ids=linked
    )


def net_worth_debt_gbp(
    accounts: list[FinanceAccount],
    liabilities: list[FinanceLiability],
) -> float:
    """Debt subtracted from assets for net worth.

    Includes debt-type account balances and liabilities that are not already
    represented by a linked debt-type account. Does not add liability totals
    a second time through category sums.
    """
    linked = _linked_account_ids(accounts, DEBT_ACCOUNT_TYPES)
    from_accounts = sum(
        account.balance_gbp for account in accounts if account.account_type in DEBT_ACCOUNT_TYPES
    )
    from_liabilities = sum_unlinked_liabilities(liabilities, exclude_account_ids=linked)
    return from_accounts + from_liabilities


def net_worth_assets_gbp(
    personal_bank: float,
    business_bank: float,
    pension: float,
    debtors: float,
) -> float:
    return personal_bank + business_bank + pension + debtors
