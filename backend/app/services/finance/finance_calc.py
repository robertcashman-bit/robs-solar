"""Canonical financial calculations for Rob's Finance.

All dashboard totals, reports, and budget inputs should flow through this
module so personal/business figures stay consistent.

Consolidated net worth
----------------------
    assets = personal cash (positive current accounts)
           + business cash (positive current accounts)
           + pension + property + other_asset + debtors

    liabilities = personal debts (ex Director's Loan)
                + business debts (ex Director's Loan)
                + overdrafts (negative current-account balances)
                + unlinked account-type debts
                  (credit_card, loan, mortgage, capital_on_tap, creditors)

    Director's Loan (credit) is money the company owes the director. It is a
    personal receivable and a company payable. It is reported separately and
    excluded from consolidated household net worth so the same IOU is not
    counted as both a personal asset and a company liability.

    VAT / corporation-tax reserve accounts are earmarked cash, not extra
    assets on top of the current-account balance.

    Unused credit limits are availability, never cash or assets.

    net_worth = assets − liabilities
"""

from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

ASSET_ACCOUNT_TYPES = frozenset({"pension", "property", "other_asset", "debtors"})
CASH_ACCOUNT_TYPES = frozenset({"current"})
RESERVE_ACCOUNT_TYPES = frozenset({"vat_reserve", "corp_tax_reserve"})
LIABILITY_ACCOUNT_TYPES = frozenset(
    {"credit_card", "loan", "mortgage", "capital_on_tap", "creditors"}
)
DLA_TYPES = frozenset({"directors_loan"})

_ACCOUNT_TO_DEBT = {
    "credit_card": "credit_card",
    "loan": "loan",
    "mortgage": "mortgage",
    "capital_on_tap": "business_loan",
    "directors_loan": "directors_loan",
    "creditors": "other",
}


@dataclass(frozen=True)
class AccountView:
    id: int
    scope: str
    account_type: str
    name: str
    balance_gbp: float
    credit_limit_gbp: float | None = None
    dla_direction: str | None = None
    is_active: bool = True
    source: str = "manual"
    provider: str = ""


@dataclass(frozen=True)
class LiabilityView:
    id: int
    scope: str
    name: str
    debt_type: str
    balance_gbp: float
    interest_rate_pct: float
    minimum_payment_gbp: float
    overpayment_gbp: float = 0.0
    account_id: int | None = None
    original_balance_gbp: float | None = None
    payment_day: int | None = None
    dla_direction: str | None = None
    interest_rate_known: bool = True
    credit_limit_gbp: float | None = None
    is_active: bool = True


@dataclass(frozen=True)
class SnapshotView:
    monthly_income_gbp: float = 0.0
    monthly_spending_gbp: float = 0.0
    household_bills_gbp: float = 0.0
    debt_repayments_gbp: float = 0.0
    turnover_gbp: float = 0.0
    expenses_gbp: float = 0.0
    vat_reserve_gbp: float = 0.0
    corp_tax_reserve_gbp: float = 0.0
    debtors_gbp: float = 0.0
    creditors_gbp: float = 0.0
    profit_estimate_gbp: float = 0.0


@dataclass(frozen=True)
class FinanceTotals:
    personal_cash_gbp: float
    business_cash_gbp: float
    available_cash_gbp: float
    personal_overdraft_gbp: float
    business_overdraft_gbp: float
    available_credit_gbp: float
    credit_limit_gbp: float
    pension_gbp: float
    property_gbp: float
    other_assets_gbp: float
    debtors_gbp: float
    total_assets_gbp: float
    personal_debt_gbp: float
    business_debt_gbp: float
    credit_card_gbp: float
    loan_gbp: float
    mortgage_gbp: float
    directors_loan_gbp: float
    creditors_gbp: float
    vat_reserve_gbp: float
    corp_tax_reserve_gbp: float
    total_liabilities_gbp: float
    net_worth_gbp: float
    monthly_income_gbp: float
    monthly_spending_gbp: float
    monthly_surplus_gbp: float
    cash_after_bills_gbp: float
    vat_reserve_warning: bool
    corp_tax_reserve_warning: bool
    debt_reduction_gbp: float
    personal_credit_card_gbp: float = 0.0
    formula: str = (
        "net_worth = (positive current + pension + property + other assets + debtors) "
        "− (active debts ex-DLA + overdrafts + unlinked account debts). "
        "Director's Loan is company-owes-director and omitted here. "
        "Credit limits are not assets."
    )


def _active_accounts(accounts: Iterable[AccountView]) -> list[AccountView]:
    return [item for item in accounts if item.is_active]


def _active_debts(liabilities: Iterable[LiabilityView]) -> list[LiabilityView]:
    return [item for item in liabilities if item.is_active]


def _norm(value: str) -> str:
    return value.strip().lower()


def is_directors_loan(value: object) -> bool:
    raw = getattr(value, "value", value)
    return str(raw) in DLA_TYPES


def is_repayable_debt(item: object) -> bool:
    """True for liabilities the household must repay. DLA is not one of them."""
    return not is_directors_loan(getattr(item, "debt_type", ""))


def linked_account_ids(liabilities: Iterable[LiabilityView]) -> set[int]:
    return {item.account_id for item in liabilities if item.account_id is not None}


def account_covered_by_liability(
    account: AccountView,
    liabilities: Iterable[LiabilityView],
) -> bool:
    """True when this account's balance is already represented as a liability."""
    debts = list(liabilities)
    if account.id in linked_account_ids(debts):
        return True
    expected = _ACCOUNT_TO_DEBT.get(account.account_type)
    account_name = _norm(account.name)
    for debt in debts:
        if _norm(debt.name) != account_name:
            continue
        if expected is None or debt.debt_type == expected or debt.debt_type == account.account_type:
            return True
        if account.account_type == "loan" and debt.debt_type == "business_loan":
            return True
    return False


def monthly_interest_gbp(balance: float, annual_rate_pct: float) -> float:
    """Approximate monthly interest for an APR-based product: balance × APR / 12."""
    if balance <= 0 or annual_rate_pct <= 0:
        return 0.0
    return round(balance * (annual_rate_pct / 100.0) / 12.0, 2)


def _revolving_accounts(accounts: Iterable[AccountView]) -> list[AccountView]:
    return [
        account
        for account in _active_accounts(accounts)
        if account.account_type in {"credit_card", "capital_on_tap"}
        and account.credit_limit_gbp is not None
    ]


REVOLVING_DEBT_TYPES = frozenset({"credit_card", "business_loan"})


def _revolving_debts(liabilities: Iterable[LiabilityView]) -> list[LiabilityView]:
    return [
        debt
        for debt in _active_debts(liabilities)
        if debt.debt_type in REVOLVING_DEBT_TYPES and debt.credit_limit_gbp is not None
    ]


def _credit_already_counted(
    debt: LiabilityView,
    accounts: Iterable[AccountView],
) -> bool:
    revolving = list(_revolving_accounts(accounts))
    if debt.account_id is not None and any(account.id == debt.account_id for account in revolving):
        return True
    debt_name = _norm(debt.name)
    return any(
        _norm(account.name) == debt_name and account.scope == debt.scope
        for account in revolving
    )


def available_credit_gbp(
    accounts: Iterable[AccountView],
    liabilities: Iterable[LiabilityView] | None = None,
) -> float:
    total = 0.0
    account_list = list(accounts)
    for account in _revolving_accounts(account_list):
        used = max(account.balance_gbp, 0.0)
        total += max((account.credit_limit_gbp or 0.0) - used, 0.0)
    for debt in _revolving_debts(liabilities or []):
        if _credit_already_counted(debt, account_list):
            continue
        used = max(debt.balance_gbp, 0.0)
        total += max((debt.credit_limit_gbp or 0.0) - used, 0.0)
    return round(total, 2)


def recorded_credit_limit_gbp(
    accounts: Iterable[AccountView],
    liabilities: Iterable[LiabilityView] | None = None,
) -> float:
    """Sum of entered revolving limits. Zero means no limit was recorded."""
    account_list = list(accounts)
    total = sum(
        max(account.credit_limit_gbp or 0.0, 0.0)
        for account in _revolving_accounts(account_list)
    )
    for debt in _revolving_debts(liabilities or []):
        if _credit_already_counted(debt, account_list):
            continue
        total += max(debt.credit_limit_gbp or 0.0, 0.0)
    return round(total, 2)


def is_sandbox_account(account: AccountView) -> bool:
    provider = (account.provider or "").strip().lower()
    name = (account.name or "").strip().lower()
    if "mock aspsp" in name or "mock aspsp" in provider:
        return True
    return account.source == "open_banking" and "sandbox" in provider


def _sum_cash(accounts: list[AccountView], scope: str) -> tuple[float, float]:
    positive = 0.0
    overdraft = 0.0
    for account in accounts:
        if account.scope != scope or account.account_type not in CASH_ACCOUNT_TYPES:
            continue
        if is_sandbox_account(account):
            continue
        if account.balance_gbp >= 0:
            positive += account.balance_gbp
        else:
            overdraft += abs(account.balance_gbp)
    return round(positive, 2), round(overdraft, 2)


def _sum_type(accounts: list[AccountView], account_type: str, scope: str | None = None) -> float:
    return round(
        sum(
            account.balance_gbp
            for account in accounts
            if account.account_type == account_type and (scope is None or account.scope == scope)
        ),
        2,
    )


def _debt_total(
    liabilities: list[LiabilityView],
    *,
    scope: str | None = None,
    exclude_dla: bool = True,
) -> float:
    total = 0.0
    for debt in liabilities:
        if scope is not None and debt.scope != scope:
            continue
        if exclude_dla and debt.debt_type in DLA_TYPES:
            continue
        total += debt.balance_gbp
    return round(total, 2)


def _unlinked_account_debts(
    accounts: list[AccountView],
    liabilities: list[LiabilityView],
) -> list[AccountView]:
    return [
        account
        for account in accounts
        if account.account_type in LIABILITY_ACCOUNT_TYPES
        and not account_covered_by_liability(account, liabilities)
    ]


def _typed_debt(
    liabilities: list[LiabilityView],
    unlinked: list[AccountView],
    debt_types: set[str],
    account_types: set[str],
) -> float:
    from_debts = sum(debt.balance_gbp for debt in liabilities if debt.debt_type in debt_types)
    from_accounts = sum(
        account.balance_gbp for account in unlinked if account.account_type in account_types
    )
    return round(from_debts + from_accounts, 2)


def compute_totals(
    accounts: Iterable[AccountView],
    liabilities: Iterable[LiabilityView],
    personal: SnapshotView | None = None,
    business: SnapshotView | None = None,
) -> FinanceTotals:
    accounts_list = [
        account
        for account in _active_accounts(accounts)
        if not is_sandbox_account(account)
    ]
    debts = _active_debts(liabilities)
    personal = personal or SnapshotView()
    business = business or SnapshotView()

    personal_cash, personal_od = _sum_cash(accounts_list, "personal")
    business_cash, business_od = _sum_cash(accounts_list, "business")
    available_cash = round(personal_cash + business_cash, 2)

    pension = _sum_type(accounts_list, "pension")
    property_gbp = _sum_type(accounts_list, "property")
    other_assets = _sum_type(accounts_list, "other_asset")
    debtor_accounts = _sum_type(accounts_list, "debtors")
    debtors = debtor_accounts if debtor_accounts > 0 else round(business.debtors_gbp, 2)

    vat_accounts = _sum_type(accounts_list, "vat_reserve")
    corp_accounts = _sum_type(accounts_list, "corp_tax_reserve")
    # VAT reserve is cash in the vat_reserve pot (e.g. QuickFile 1210 Vat Account).
    # Snapshot vat_reserve_gbp was historically filled with creditor VAT liability
    # (2200+2202); never let that overwrite a real pot balance, even a tiny one.
    has_vat_account = any(account.account_type == "vat_reserve" for account in accounts_list)
    vat_reserve = vat_accounts if has_vat_account else round(business.vat_reserve_gbp, 2)
    corp_reserve = (
        round(business.corp_tax_reserve_gbp, 2)
        if business.corp_tax_reserve_gbp > 0
        else corp_accounts
    )

    personal_debt = _debt_total(debts, scope="personal")
    business_debt = _debt_total(debts, scope="business")
    unlinked = _unlinked_account_debts(accounts_list, debts)
    unlinked_total = round(sum(account.balance_gbp for account in unlinked), 2)

    creditor_accounts = sum(a.balance_gbp for a in unlinked if a.account_type == "creditors")
    creditors = (
        round(creditor_accounts, 2) if creditor_accounts > 0 else round(business.creditors_gbp, 2)
    )

    dla_debts = sum(debt.balance_gbp for debt in debts if debt.debt_type in DLA_TYPES)
    dla_accounts = sum(
        account.balance_gbp
        for account in accounts_list
        if account.account_type in DLA_TYPES and not account_covered_by_liability(account, debts)
    )
    directors_loan = round(dla_debts + dla_accounts, 2)

    credit_cards = _typed_debt(debts, unlinked, {"credit_card"}, {"credit_card"})
    personal_credit_cards = _typed_debt(
        [debt for debt in debts if debt.scope == "personal"],
        [account for account in unlinked if account.scope == "personal"],
        {"credit_card"},
        {"credit_card"},
    )
    loans = _typed_debt(debts, unlinked, {"loan", "business_loan"}, {"loan", "capital_on_tap"})
    mortgage = _typed_debt(debts, unlinked, {"mortgage"}, {"mortgage"})

    total_assets = round(
        personal_cash + business_cash + pension + property_gbp + other_assets + debtors,
        2,
    )
    total_liabilities = round(
        personal_debt + business_debt + personal_od + business_od + unlinked_total,
        2,
    )
    # Snapshot creditors only if no creditor accounts were already included.
    if creditor_accounts <= 0 and business.creditors_gbp > 0:
        total_liabilities = round(total_liabilities + business.creditors_gbp, 2)

    net_worth = round(total_assets - total_liabilities, 2)

    monthly_income = personal.monthly_income_gbp
    monthly_spending = personal.monthly_spending_gbp
    monthly_surplus = round(
        monthly_income - monthly_spending - personal.debt_repayments_gbp,
        2,
    )
    cash_after_bills = round(personal_cash - personal_od - personal.household_bills_gbp, 2)

    profit = business.profit_estimate_gbp or (business.turnover_gbp - business.expenses_gbp)
    has_business = (
        business.turnover_gbp > 0
        or business.expenses_gbp > 0
        or business_cash > 0
        or vat_reserve > 0
        or corp_reserve > 0
    )
    vat_warning = has_business and vat_reserve < (
        business.expenses_gbp * 0.2 if business.expenses_gbp else 500
    )
    corp_warning = has_business and profit > 0 and corp_reserve < (profit * 0.19)

    debt_reduction = 0.0
    for debt in debts:
        original = debt.original_balance_gbp
        if original is not None and original > debt.balance_gbp:
            debt_reduction += original - debt.balance_gbp

    return FinanceTotals(
        personal_cash_gbp=personal_cash,
        business_cash_gbp=business_cash,
        available_cash_gbp=available_cash,
        personal_overdraft_gbp=personal_od,
        business_overdraft_gbp=business_od,
        available_credit_gbp=available_credit_gbp(accounts_list, debts),
        credit_limit_gbp=recorded_credit_limit_gbp(accounts_list, debts),
        pension_gbp=pension,
        property_gbp=property_gbp,
        other_assets_gbp=other_assets,
        debtors_gbp=debtors,
        total_assets_gbp=total_assets,
        personal_debt_gbp=personal_debt,
        business_debt_gbp=business_debt,
        credit_card_gbp=credit_cards,
        personal_credit_card_gbp=personal_credit_cards,
        loan_gbp=loans,
        mortgage_gbp=mortgage,
        directors_loan_gbp=directors_loan,
        creditors_gbp=creditors,
        vat_reserve_gbp=vat_reserve,
        corp_tax_reserve_gbp=corp_reserve,
        total_liabilities_gbp=total_liabilities,
        net_worth_gbp=net_worth,
        monthly_income_gbp=round(monthly_income, 2),
        monthly_spending_gbp=round(monthly_spending, 2),
        monthly_surplus_gbp=monthly_surplus,
        cash_after_bills_gbp=cash_after_bills,
        vat_reserve_warning=vat_warning,
        corp_tax_reserve_warning=corp_warning,
        debt_reduction_gbp=round(debt_reduction, 2),
    )


def accounts_from_schema(accounts: Iterable[object]) -> list[AccountView]:
    views: list[AccountView] = []
    for item in accounts:
        views.append(
            AccountView(
                id=int(getattr(item, "id")),
                scope=_scope_value(getattr(item, "scope")),
                account_type=_enum_value(getattr(item, "account_type")),
                name=str(getattr(item, "name")),
                balance_gbp=float(getattr(item, "balance_gbp")),
                credit_limit_gbp=_optional_float(getattr(item, "credit_limit_gbp", None)),
                dla_direction=_optional_str(getattr(item, "dla_direction", None)),
                is_active=bool(getattr(item, "is_active", True)),
                source=_enum_value(getattr(item, "source", "manual")) or "manual",
                provider=str(getattr(item, "provider", "") or ""),
            )
        )
    return views


def liabilities_from_schema(liabilities: Iterable[object]) -> list[LiabilityView]:
    views: list[LiabilityView] = []
    for item in liabilities:
        views.append(
            LiabilityView(
                id=int(getattr(item, "id")),
                scope=_scope_value(getattr(item, "scope")),
                name=str(getattr(item, "name")),
                debt_type=_enum_value(getattr(item, "debt_type")),
                balance_gbp=float(getattr(item, "balance_gbp")),
                interest_rate_pct=float(getattr(item, "interest_rate_pct")),
                minimum_payment_gbp=float(getattr(item, "minimum_payment_gbp")),
                overpayment_gbp=float(getattr(item, "overpayment_gbp", 0.0) or 0.0),
                account_id=_optional_int(getattr(item, "account_id", None)),
                original_balance_gbp=_optional_float(getattr(item, "original_balance_gbp", None)),
                payment_day=_optional_int(getattr(item, "payment_day", None)),
                dla_direction=_optional_str(getattr(item, "dla_direction", None)),
                interest_rate_known=(
                    True
                    if getattr(item, "interest_rate_known", True) is None
                    else bool(getattr(item, "interest_rate_known", True))
                ),
                credit_limit_gbp=_optional_float(getattr(item, "credit_limit_gbp", None)),
                is_active=bool(getattr(item, "is_active", True)),
            )
        )
    return views


def personal_snapshot_view(snapshot: object | None) -> SnapshotView | None:
    if snapshot is None:
        return None
    return SnapshotView(
        monthly_income_gbp=float(getattr(snapshot, "monthly_income_gbp", 0.0) or 0.0),
        monthly_spending_gbp=float(getattr(snapshot, "monthly_spending_gbp", 0.0) or 0.0),
        household_bills_gbp=float(getattr(snapshot, "household_bills_gbp", 0.0) or 0.0),
        debt_repayments_gbp=float(getattr(snapshot, "debt_repayments_gbp", 0.0) or 0.0),
    )


def business_snapshot_view(snapshot: object | None) -> SnapshotView | None:
    if snapshot is None:
        return None
    return SnapshotView(
        turnover_gbp=float(getattr(snapshot, "turnover_gbp", 0.0) or 0.0),
        expenses_gbp=float(getattr(snapshot, "expenses_gbp", 0.0) or 0.0),
        vat_reserve_gbp=float(getattr(snapshot, "vat_reserve_gbp", 0.0) or 0.0),
        corp_tax_reserve_gbp=float(getattr(snapshot, "corp_tax_reserve_gbp", 0.0) or 0.0),
        debtors_gbp=float(getattr(snapshot, "debtors_gbp", 0.0) or 0.0),
        creditors_gbp=float(getattr(snapshot, "creditors_gbp", 0.0) or 0.0),
        profit_estimate_gbp=float(getattr(snapshot, "profit_estimate_gbp", 0.0) or 0.0),
    )


def _scope_value(value: object) -> str:
    return _enum_value(value)


def _enum_value(value: object) -> str:
    raw = getattr(value, "value", value)
    return str(raw)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    text = str(raw).strip()
    return text or None


def previous_month_key(month: str) -> str:
    year_str, month_str = month.split("-", 1)
    year = int(year_str)
    month_n = int(month_str)
    if month_n <= 1:
        return f"{year - 1}-12"
    return f"{year}-{month_n - 1:02d}"


def next_payment_date(payment_day: int, today: date | None = None) -> date:
    today = today or date.today()
    day = min(max(int(payment_day), 1), 31)
    last = monthrange(today.year, today.month)[1]
    candidate = date(today.year, today.month, min(day, last))
    if candidate < today:
        if today.month == 12:
            nxt = date(today.year + 1, 1, 1)
        else:
            nxt = date(today.year, today.month + 1, 1)
        last = monthrange(nxt.year, nxt.month)[1]
        candidate = date(nxt.year, nxt.month, min(day, last))
    return candidate


def upcoming_payments(
    liabilities: Iterable[LiabilityView],
    *,
    today: date | None = None,
    within_days: int = 14,
) -> list[dict[str, object]]:
    today = today or date.today()
    horizon = today + timedelta(days=within_days)
    rows: list[dict[str, object]] = []
    for item in _active_debts(liabilities):
        if item.payment_day is None:
            continue
        amount = item.minimum_payment_gbp + item.overpayment_gbp
        if amount <= 0:
            continue
        due = next_payment_date(item.payment_day, today)
        if due > horizon:
            continue
        rows.append(
            {
                "name": item.name,
                "scope": item.scope,
                "amount_gbp": round(amount, 2),
                "due_date": due.isoformat(),
                "days_until": (due - today).days,
            }
        )
    rows.sort(key=lambda row: (int(row["days_until"]), str(row["name"])))
    return rows


def resolve_dla_direction(item: AccountView | LiabilityView) -> str:
    raw = (item.dla_direction or "").strip()
    if raw in {"director_owes_company", "company_owes_director"}:
        return raw
    if item.scope == "personal":
        return "director_owes_company"
    return "company_owes_director"


def directors_loan_sides(
    accounts: Iterable[AccountView],
    liabilities: Iterable[LiabilityView],
) -> tuple[float, float]:
    accounts_list = _active_accounts(accounts)
    debts = _active_debts(liabilities)
    director_owes = 0.0
    company_owes = 0.0
    for item in debts:
        if item.debt_type not in DLA_TYPES:
            continue
        if resolve_dla_direction(item) == "director_owes_company":
            director_owes += item.balance_gbp
        else:
            company_owes += item.balance_gbp
    for account in accounts_list:
        if account.account_type not in DLA_TYPES:
            continue
        if account_covered_by_liability(account, debts):
            continue
        if resolve_dla_direction(account) == "director_owes_company":
            director_owes += account.balance_gbp
        else:
            company_owes += account.balance_gbp
    return round(director_owes, 2), round(company_owes, 2)


def personal_net_worth(
    *,
    personal_bank: float,
    pension: float,
    personal_external_debt: float,
    property_gbp: float = 0.0,
    other_assets_gbp: float = 0.0,
    director_owes_company: float = 0.0,
    company_owes_director: float = 0.0,
) -> float:
    """Personal stack only: cash + pension + house/other assets − personal debts ± DLA.

    Property and other personal assets belong here (not on company_position).
    Combined net worth already includes them via total_assets.
    """
    return round(
        personal_bank
        + pension
        + property_gbp
        + other_assets_gbp
        + company_owes_director
        - personal_external_debt
        - director_owes_company,
        2,
    )


def company_position(
    *,
    business_bank: float,
    debtors: float,
    vat_reserve: float,
    corp_tax_reserve: float,
    business_external_debt: float,
    director_owes_company: float = 0.0,
    company_owes_director: float = 0.0,
) -> float:
    return round(
        business_bank
        + debtors
        + vat_reserve
        + corp_tax_reserve
        + director_owes_company
        - business_external_debt
        - company_owes_director,
        2,
    )


def external_debt_gbp(
    personal_debt: float,
    business_debt: float,
    directors_loan: float = 0.0,
) -> float:
    """Third-party debt. Personal/business totals already exclude director's loan."""
    del directors_loan
    return round(max(personal_debt + business_debt, 0.0), 2)


def monthly_interest_from_debts(
    liabilities: Iterable[LiabilityView],
) -> tuple[float, bool]:
    total = 0.0
    incomplete = False
    for item in _active_debts(liabilities):
        if not item.interest_rate_known:
            incomplete = True
            continue
        total += monthly_interest_gbp(item.balance_gbp, item.interest_rate_pct)
    return round(total, 2), incomplete


def high_interest_debt_gbp(
    liabilities: Iterable[LiabilityView],
    *,
    threshold_pct: float = 15.0,
) -> float:
    total = 0.0
    for item in _active_debts(liabilities):
        if not item.interest_rate_known:
            continue
        if item.interest_rate_pct >= threshold_pct:
            total += item.balance_gbp
    return round(total, 2)


def instrument_configured(
    accounts: Iterable[AccountView],
    liabilities: Iterable[LiabilityView],
    *,
    account_type: str,
    debt_type: str | None = None,
) -> bool:
    if any(account.account_type == account_type for account in _active_accounts(accounts)):
        return True
    if debt_type is None:
        return False
    return any(item.debt_type == debt_type for item in _active_debts(liabilities))


@dataclass(frozen=True)
class MonthlyFlow:
    income_gbp: float = 0.0
    spending_gbp: float = 0.0
    as_of: str = ""

    def has_values(self) -> bool:
        return self.income_gbp > 0 or self.spending_gbp > 0


def pick_open_banking_flow(*sources: MonthlyFlow) -> MonthlyFlow:
    """Use the newest non-empty Open Banking cache.

    Lunch Flow and TrueLayer can describe the same bank, so the figures are
    not added together. An empty source is ignored so a TrueLayer-only setup
    still feeds the open-banking fallback.
    """
    nonempty = [item for item in sources if item.has_values()]
    if not nonempty:
        return MonthlyFlow()
    return max(nonempty, key=lambda item: item.as_of)


def monthly_flow_note(source: str | None) -> str:
    """Human label for monthly income/spend source (actual vs plan vs none)."""
    key = (source or "none").strip().lower()
    if key == "snapshot":
        return "From the latest personal snapshot"
    if key == "open_banking":
        return "From live Open Banking sync (last 30 days)"
    if key == "cashflow":
        return "From confirmed cash-flow entries"
    if key == "budget":
        return "Budget plan estimate — not live income or spending"
    if key == "transactions":
        return "From imported personal transactions (transfers excluded)"
    return "No live sync, snapshot, or budget plan for this month"


def resolve_monthly_flow(
    *,
    snapshot_present: bool,
    snapshot_income: float = 0.0,
    snapshot_spending: float = 0.0,
    snapshot_bills: float = 0.0,
    snapshot_repayments: float = 0.0,
    open_banking_income: float = 0.0,
    open_banking_spending: float = 0.0,
    cashflow_income: float = 0.0,
    cashflow_spending: float = 0.0,
    cashflow_bills: float = 0.0,
    budget_income: float = 0.0,
    budget_spending: float = 0.0,
) -> tuple[float, float, float, float, str, bool]:
    snapshot_has_values = (
        snapshot_income > 0
        or snapshot_spending > 0
        or snapshot_bills > 0
        or snapshot_repayments > 0
    )
    if snapshot_present and snapshot_has_values:
        return (
            round(snapshot_income, 2),
            round(snapshot_spending, 2),
            round(snapshot_bills, 2),
            round(snapshot_repayments, 2),
            "snapshot",
            True,
        )
    if open_banking_income > 0 or open_banking_spending > 0:
        return (
            round(open_banking_income, 2),
            round(open_banking_spending, 2),
            0.0,
            round(snapshot_repayments, 2) if snapshot_present else 0.0,
            "open_banking",
            True,
        )
    if cashflow_income > 0 or cashflow_spending > 0 or cashflow_bills > 0:
        return (
            round(cashflow_income, 2),
            round(cashflow_spending, 2),
            round(cashflow_bills, 2),
            round(snapshot_repayments, 2) if snapshot_present else 0.0,
            "cashflow",
            True,
        )
    if budget_income > 0 or budget_spending > 0:
        return (
            round(budget_income, 2),
            round(budget_spending, 2),
            0.0,
            round(snapshot_repayments, 2) if snapshot_present else 0.0,
            "budget",
            True,
        )
    if snapshot_present:
        return (
            round(snapshot_income, 2),
            round(snapshot_spending, 2),
            round(snapshot_bills, 2),
            round(snapshot_repayments, 2),
            "snapshot",
            True,
        )
    return 0.0, 0.0, 0.0, 0.0, "none", False
