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
    business_credit_card_gbp: float = 0.0
    personal_loan_gbp: float = 0.0
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


REVOLVING_DEBT_TYPES = frozenset({"credit_card", "business_loan", "loan"})


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
    business_credit_cards = _typed_debt(
        [debt for debt in debts if debt.scope == "business"],
        [account for account in unlinked if account.scope == "business"],
        {"credit_card"},
        {"credit_card"},
    )
    # Personal loans only — never mix into the business loans tile.
    personal_loans = _typed_debt(
        [debt for debt in debts if debt.scope == "personal"],
        [account for account in unlinked if account.scope == "personal"],
        {"loan"},
        {"loan"},
    )
    # Business loans / capital-on-tap only (mortgage stays personal, not a loan).
    business_loans = _typed_debt(
        [debt for debt in debts if debt.scope == "business"],
        [account for account in unlinked if account.scope == "business"],
        {"loan", "business_loan"},
        {"loan", "capital_on_tap"},
    )
    mortgage = _typed_debt(
        [debt for debt in debts if debt.scope == "personal"],
        [account for account in unlinked if account.scope == "personal"],
        {"mortgage"},
        {"mortgage"},
    )

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
        business_credit_card_gbp=business_credit_cards,
        loan_gbp=business_loans,
        personal_loan_gbp=personal_loans,
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
                original_balance_gbp=sanitize_mortgage_original_balance(
                    _enum_value(getattr(item, "debt_type")),
                    _optional_float(getattr(item, "original_balance_gbp", None)),
                ),
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


@dataclass(frozen=True)
class OverviewLine:
    """Plain-English line for the Overview You / Defence Legal columns."""

    key: str
    label: str
    amount_gbp: float | None = None
    kind: str = "asset"  # asset | debt | gap
    tier: str = "primary"  # primary | more
    hint: str = ""


@dataclass(frozen=True)
class OverviewSideBreakdown:
    side: str  # personal | business
    owned_total_gbp: float
    owed_total_gbp: float
    whats_left_gbp: float | None
    owned: tuple[OverviewLine, ...]
    owed: tuple[OverviewLine, ...]
    whats_left_hint: str = ""
    whats_left_available: bool = True


_VEHICLE_DEBT_TOKENS = (
    "tesla",
    "vehicle",
    "hire purchase",
    "hire-purchase",
    "motor finance",
    "car finance",
    "af-63591",
    "7090442480",
)
_VEHICLE_ASSET_TOKENS = ("tesla", "vehicle", "car", "model 3", "model y")
# QuickFile HP Finance only (0050 / 50) — remaining capital for Tesla.
# 2300 Loans is a current-asset debit on Defence Legal, NOT the HP tail and
# NOT money lent out: ledger drill shows Funding Circle / BBL / Flexipay
# repayments (plus two Tesla HP instalments misposted here) dumped on 2300,
# flipping it to a debit asset. Loan liabilities for those facilities are
# missing from the BS — do not invent them; Overview still 1:1s the sheet.
_QF_HP_NOMINALS = frozenset({"50"})
_QF_HP_LABEL_TOKENS = (
    "hp finance",
    "hire purchase",
    "hire-purchase",
)
_QF_LOANS_ASSET_NOMINALS = frozenset({"2300"})
_QF_VAT_LIABILITY_NOMINALS = frozenset({"2200", "2202"})
# Debit balances on liability nominals that QuickFile section *totals* treat as
# current assets (prepaid / overpaid) — never list these on Owe.
_QF_PREPAID_LIABILITY_AS_ASSET_NOMINALS = frozenset({"2204", "2230"})
# Leftovers small enough to hide behind More (not real debts).
_MORE_LEFTOVER_GBP = 3000.0


def _text_has_token(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token in lowered for token in tokens)


def _normalize_nominal(code: str | None) -> str:
    digits = "".join(ch for ch in str(code or "") if ch.isdigit())
    return digits.lstrip("0") or (digits if digits else "")


def _is_qf_hp_finance_line(line: dict) -> bool:
    """True for QuickFile HP Finance (50) — Tesla remaining capital."""
    code = _normalize_nominal(str(line.get("nominal_code") or ""))
    if code in _QF_HP_NOMINALS:
        return True
    label = str(line.get("label") or "").strip().lower()
    return bool(label) and _text_has_token(label, _QF_HP_LABEL_TOKENS)


def _is_qf_loans_asset_line(line: dict) -> bool:
    """True for QuickFile 2300 Loans when it is a current-asset debit.

    On Defence Legal this is a repayments dump (Funding Circle, BBL, etc.),
    not cash owed to the company and not Tesla HP (that is 0050).
    """
    code = _normalize_nominal(str(line.get("nominal_code") or ""))
    if code in _QF_LOANS_ASSET_NOMINALS:
        return True
    label = str(line.get("label") or "").strip().lower()
    return label in {"loans", "loan", "bank loan", "bank loans"}


def _is_qf_vat_liability_line(line: dict) -> bool:
    code = _normalize_nominal(str(line.get("nominal_code") or ""))
    if code in _QF_VAT_LIABILITY_NOMINALS:
        return True
    label = str(line.get("label") or "").strip().lower()
    return bool(label) and (
        "vat liability" in label
        or "sales tax" in label
        or label in {"vat", "vat control", "sales tax control"}
    )


def _is_qf_prepaid_liability_as_asset(line: dict) -> bool:
    """True for 2204 / 2230 debit balances filed under Current liabilities.

    QuickFile may list Manual Adjustments and Pension Fund under liability
    lines while section totals count the same amounts in current assets.
    Those are prepaid/overpaid balances — Own, never Owe.
    """
    code = _normalize_nominal(str(line.get("nominal_code") or ""))
    if code in _QF_PREPAID_LIABILITY_AS_ASSET_NOMINALS:
        return True
    label = str(line.get("label") or "").strip().lower()
    if "manual adjustment" in label:
        return True
    if "pension fund" in label:
        return True
    return False


def _qf_hp_finance_gbp(liability_lines: list[dict]) -> float:
    total = 0.0
    for line in liability_lines:
        if _is_qf_hp_finance_line(line):
            total += abs(float(line.get("amount_gbp") or 0))
    return round(total, 2)


def _qf_loans_asset_gbp(asset_lines: list[dict]) -> float:
    total = 0.0
    for line in asset_lines:
        if _is_qf_loans_asset_line(line):
            total += abs(float(line.get("amount_gbp") or 0))
    return round(total, 2)


def _is_qf_hp_or_vehicle_loan_line(line: dict) -> bool:
    """Back-compat alias: HP Finance only (never 2300)."""
    return _is_qf_hp_finance_line(line)


def _qf_hp_absorbed_gbp(liability_lines: list[dict], *, vehicle_hp_total: float) -> float:
    """QF HP Finance already represented by the named Tesla line."""
    if vehicle_hp_total <= 0 and _qf_hp_finance_gbp(liability_lines) <= 0:
        return 0.0
    return _qf_hp_finance_gbp(liability_lines)


def _plain_qf_asset_line(line: dict) -> OverviewLine | None:
    """Map one QuickFile current-asset line to plain English. Skip zeros."""
    amount = round(abs(float(line.get("amount_gbp") or 0)), 2)
    if amount <= 0.005:
        return None
    code = _normalize_nominal(str(line.get("nominal_code") or ""))
    raw_label = str(line.get("label") or "").strip()

    if code == "1100" or "debtors" in raw_label.lower():
        return OverviewLine(
            "customers_owe",
            "Customers still to pay",
            amount,
            "asset",
            "primary",
        )
    if code == "1200" or raw_label.lower() in {
        "current",
        "current account",
        "bank",
        "bank account",
    }:
        return OverviewLine("business_bank", "Bank", amount, "asset", "primary")
    if code == "1210" or "vat account" in raw_label.lower():
        return OverviewLine(
            "vat_account",
            "VAT account",
            amount,
            "asset",
            "more" if amount < _MORE_LEFTOVER_GBP else "primary",
        )
    if code == "2100" or "creditors control" in raw_label.lower():
        # Debit creditors control = unallocated supplier payments / other company money.
        # Never label this "Suppliers still to pay".
        return OverviewLine(
            "creditors_debit",
            "Other company money",
            amount,
            "asset",
            "primary",
            "Unallocated supplier payments (QuickFile 2100 debit)",
        )
    if code == "2204" or "manual adjustment" in raw_label.lower():
        return OverviewLine(
            "manual_adjustments",
            "Manual adjustments",
            amount,
            "asset",
            "more" if amount < _MORE_LEFTOVER_GBP else "primary",
        )
    if code == "2230" or "pension" in raw_label.lower():
        return OverviewLine(
            "pension_fund",
            "Pension fund",
            amount,
            "asset",
            "more" if amount < _MORE_LEFTOVER_GBP else "primary",
        )
    if _is_qf_loans_asset_line(line):
        return OverviewLine(
            "qf_loans_asset",
            "Loan repayments (on the books as an asset)",
            amount,
            "asset",
            "primary",
            "QuickFile 2300 holds loan repayment postings on the books — "
            "not money owed to the company, not Tesla HP (that is 0050). "
            "Do not invent a remaining loan balance from this line.",
        )
    label = raw_label or f"Nominal {code or '?'}"
    return OverviewLine(
        f"qf_asset_{code or 'x'}",
        label,
        amount,
        "asset",
        "more" if amount < _MORE_LEFTOVER_GBP else "primary",
    )


def _plain_qf_liability_key_label(line: dict) -> tuple[str, str, str] | None:
    """Return (key, label, hint) for a named QF liability, or None if VAT/HP handled elsewhere."""
    code = _normalize_nominal(str(line.get("nominal_code") or ""))
    raw_label = str(line.get("label") or "").strip()
    lowered = raw_label.lower()

    if _is_qf_hp_finance_line(line) or _is_qf_vat_liability_line(line):
        return None
    if _is_qf_prepaid_liability_as_asset(line):
        return None
    if code == "1201" or "director" in lowered and "loan" in lowered:
        return (
            "company_owes_robert_biz",
            "Company still owes Robert",
            "",
        )
    if code == "1207" or "overdraft" in lowered:
        return ("business_od", "Overdraft", "")
    if code == "1211" or lowered == "holding":
        return ("holding", "Holding", "")
    if code == "1258" or ("lloyds" in lowered and "card" in lowered):
        return ("lloyds_card", "Lloyds card", "")
    if code == "1259" or "capital on tap" in lowered:
        return ("capital_on_tap", "Capital on Tap", "")
    label = raw_label or f"Nominal {code or '?'}"
    return (f"qf_liab_{code or 'x'}", label, "")


def _dls_from_quickfile_balance_sheet(
    *,
    fixed_assets: float,
    current_assets: float,
    current_liab: float,
    long_liab: float,
    capital: float,
    asset_lines: list[dict],
    liability_lines: list[dict],
) -> tuple[list[OverviewLine], list[OverviewLine], float, float, float]:
    """Defence Legal column as a plain-English 1:1 of the stored QuickFile BS.

    Does not mix Lunch Flow bank balances or the debt register. Register is
    only used when no balance sheet is present (see caller).

    Pile headers always use official section totals (fixed+current,
    current+long). Leftover is official capital & reserves. Debit liability
    nominals 2204 / 2230 are Own (Manual adjustments / Pension fund), never Owe.
    """
    owned: list[OverviewLine] = []
    if fixed_assets > 0.005:
        owned.append(
            OverviewLine(
                "fixed_assets",
                "Vehicles and kit",
                round(fixed_assets, 2),
                "asset",
                "primary",
                "From the Defence Legal balance sheet",
            )
        )

    # 2204 / 2230 may sit in liability_lines while QF section totals already
    # count them in current_assets. Peel them onto Own under real names.
    prepaid_as_asset = [
        line for line in liability_lines if _is_qf_prepaid_liability_as_asset(line)
    ]
    debt_liability_lines = [
        line for line in liability_lines if not _is_qf_prepaid_liability_as_asset(line)
    ]

    # Merge duplicate keys (e.g. multiple debtors lines) by summing.
    owned_by_key: dict[str, OverviewLine] = {}
    for line in list(asset_lines) + prepaid_as_asset:
        mapped = _plain_qf_asset_line(line)
        if mapped is None:
            continue
        existing = owned_by_key.get(mapped.key)
        if existing is None:
            owned_by_key[mapped.key] = mapped
        else:
            owned_by_key[mapped.key] = OverviewLine(
                existing.key,
                existing.label,
                round(float(existing.amount_gbp or 0) + float(mapped.amount_gbp or 0), 2),
                existing.kind,
                existing.tier,
                existing.hint,
            )
    # Stable-ish order: Bank, customers, loans, then the rest.
    preferred_own = (
        "business_bank",
        "customers_owe",
        "qf_loans_asset",
        "creditors_debit",
        "vat_account",
        "manual_adjustments",
        "pension_fund",
    )
    for key in preferred_own:
        if key in owned_by_key:
            owned.append(owned_by_key.pop(key))
    owned.extend(owned_by_key.values())

    owed: list[OverviewLine] = []
    # Tesla from HP Finance (50) only — never invent market value, never use 2300.
    tesla = _qf_hp_finance_gbp(debt_liability_lines)
    if tesla > 0.005:
        owed.append(
            OverviewLine(
                "vehicle_hp_qf",
                "Tesla still to pay",
                tesla,
                "debt",
                "primary",
                "QuickFile HP Finance remaining capital",
            )
        )

    vat_total = round(
        sum(
            abs(float(line.get("amount_gbp") or 0))
            for line in debt_liability_lines
            if _is_qf_vat_liability_line(line)
        ),
        2,
    )
    holding_amount = 0.0
    owed_by_key: dict[str, OverviewLine] = {}
    for line in debt_liability_lines:
        if _is_qf_hp_finance_line(line) or _is_qf_vat_liability_line(line):
            continue
        mapped = _plain_qf_liability_key_label(line)
        if mapped is None:
            continue
        key, label, hint = mapped
        amount = round(abs(float(line.get("amount_gbp") or 0)), 2)
        if amount <= 0.005:
            continue
        if key == "holding":
            holding_amount = round(holding_amount + amount, 2)
            continue
        tier = "primary"
        existing = owed_by_key.get(key)
        if existing is None:
            owed_by_key[key] = OverviewLine(key, label, amount, "debt", tier, hint)
        else:
            owed_by_key[key] = OverviewLine(
                existing.key,
                existing.label,
                round(float(existing.amount_gbp or 0) + amount, 2),
                "debt",
                tier,
                existing.hint,
            )

    preferred_owe = (
        "business_od",
        "lloyds_card",
        "capital_on_tap",
        "company_owes_robert_biz",
    )
    for key in preferred_owe:
        if key in owed_by_key:
            owed.append(owed_by_key.pop(key))
    owed.extend(owed_by_key.values())

    # VAT as one plain line (2200 + 2202). Holding (£6) stays its own More line.
    if vat_total > 0.005:
        owed.append(
            OverviewLine(
                "vat_owed",
                "VAT",
                vat_total,
                "debt",
                "primary",
            )
        )
    if holding_amount > 0.005:
        owed.append(
            OverviewLine(
                "holding",
                "Holding",
                holding_amount,
                "debt",
                "more" if holding_amount < 50 else "primary",
            )
        )

    # Official section totals for pile headers — not line-walk sums.
    owned_total = round(fixed_assets + current_assets, 2)
    owed_total = round(current_liab + long_liab, 2)
    listed_owned = _sum_line_amounts(owned)
    listed_owed = _sum_line_amounts(owed)
    owned_gap = round(owned_total - listed_owned, 2)
    owed_gap = round(owed_total - listed_owed, 2)
    # Pad only true incomplete line walks. When QF netted the same amount into
    # asset totals and out of liability totals (e.g. 2204+2230 already rehomed
    # onto Own, or still mirrored as ±gap), do NOT invent "Other company money".
    if owned_gap > 0.01 and abs(owned_gap + owed_gap) > 0.01:
        owned.append(
            OverviewLine(
                "bs_other_owned",
                "Other company money",
                owned_gap,
                "asset",
                "primary",
            )
        )
        listed_owned = _sum_line_amounts(owned)
        owned_gap = round(owned_total - listed_owned, 2)
    if owed_gap > 0.01:
        # Only when liability_lines were incomplete — not a named-line plug.
        # Never pad a negative gap (lines exceed official) as extra debt.
        owed.append(
            OverviewLine(
                "bs_other_owed",
                "Other QuickFile creditors",
                owed_gap,
                "debt",
                "more" if owed_gap < _MORE_LEFTOVER_GBP else "primary",
            )
        )
        listed_owed = _sum_line_amounts(owed)

    left = round(float(capital), 2)
    # Prefer identity own − owe == capital when within 1p of official capital.
    identity = round(owned_total - owed_total, 2)
    if abs(identity - left) <= 0.01:
        left = identity
    return owned, owed, owned_total, owed_total, left


def _is_vehicle_hp_debt(debt: LiabilityView) -> bool:
    if debt.scope != "business" or not debt.is_active:
        return False
    if debt.debt_type in DLA_TYPES:
        return False
    return _text_has_token(debt.name, _VEHICLE_DEBT_TOKENS)


def _is_vehicle_asset(account: AccountView) -> bool:
    if account.scope != "business" or not account.is_active:
        return False
    if account.account_type != "other_asset":
        return False
    return _text_has_token(account.name, _VEHICLE_ASSET_TOKENS)


def _plain_debt_label(debt: LiabilityView) -> str:
    name = debt.name.strip()
    if _text_has_token(name, ("tesla",)):
        return "Tesla still to pay"
    if debt.debt_type == "mortgage":
        return "House mortgage"
    if debt.debt_type == "credit_card":
        return name if name else "Credit card"
    if debt.debt_type in {"loan", "business_loan"}:
        return name if name else "Loan"
    return name or "Debt"


_EXPENSIVE_APR_PCT = 15.0


def _expensive_apr_hint(debts: Iterable[LiabilityView]) -> str:
    """Plain-English label for the dearest known APR — never colour-only."""
    expensive: list[tuple[float, str]] = []
    for debt in debts:
        if not debt.is_active or debt.balance_gbp <= 0:
            continue
        if not debt.interest_rate_known:
            continue
        apr = float(debt.interest_rate_pct or 0)
        if apr < _EXPENSIVE_APR_PCT:
            continue
        expensive.append((apr, debt.name.strip() or "Debt"))
    if not expensive:
        return ""
    expensive.sort(key=lambda item: (-item[0], item[1].lower()))
    top_apr, top_name = expensive[0]
    if len(expensive) == 1:
        return f"Most expensive APR: {top_name} at {top_apr:.1f}%"
    return (
        f"Most expensive APR: {top_name} at {top_apr:.1f}% "
        f"({len(expensive)} costly debts)"
    )


def _sum_line_amounts(lines: list[OverviewLine]) -> float:
    return round(
        sum(float(line.amount_gbp) for line in lines if line.amount_gbp is not None),
        2,
    )


def build_overview_side_breakdowns(
    *,
    totals: FinanceTotals,
    accounts: Iterable[AccountView],
    liabilities: Iterable[LiabilityView],
    director_owes_company: float,
    company_owes_director: float,
    personal_whats_left: float,
    mortgage_configured: bool,
    pension_configured: bool,
    balance_sheet: dict[str, float] | None = None,
) -> tuple[OverviewSideBreakdown, OverviewSideBreakdown]:
    """You / Defence Legal columns for Overview.

    Real debts and fixed assets are always ``tier=primary`` (first paint).
    ``More`` is only for small leftovers such as a VAT pot.

    When a stored QuickFile balance sheet is present, Defence Legal is a
    plain-English 1:1 of that sheet (capital & reserves for what's left;
    asset_lines / liability_lines for own / owe). Lunch Flow and the debt
    register are not mixed in — register is fallback only if the BS is missing.
    """
    account_list = [a for a in accounts if a.is_active]
    debt_list = [d for d in liabilities if d.is_active]

    personal_cash = totals.personal_cash_gbp
    business_cash = totals.business_cash_gbp

    personal_other = round(
        sum(
            a.balance_gbp
            for a in account_list
            if a.scope == "personal" and a.account_type == "other_asset"
        ),
        2,
    )

    # --- You: own ---
    personal_owned: list[OverviewLine] = [
        OverviewLine("personal_bank", "Bank", personal_cash, "asset", "primary"),
    ]
    if totals.property_gbp > 0 or mortgage_configured:
        personal_owned.append(
            OverviewLine(
                "house_share",
                "House share",
                totals.property_gbp if totals.property_gbp > 0 else None,
                "asset",
                "primary",
                "Your half only" if totals.property_gbp > 0 else "House value not set yet",
            )
        )
    if pension_configured or totals.pension_gbp > 0:
        personal_owned.append(
            OverviewLine(
                "pension",
                "Pension",
                totals.pension_gbp if pension_configured else None,
                "asset",
                "primary",
                "" if pension_configured else "Add a pension to track this",
            )
        )
    if company_owes_director > 0:
        personal_owned.append(
            OverviewLine(
                "company_owes_robert",
                "Company still owes Robert",
                company_owes_director,
                "asset",
                "primary",
            )
        )
    if personal_other > 0:
        personal_owned.append(
            OverviewLine(
                "personal_other",
                "Other",
                personal_other,
                "asset",
                "more" if personal_other < _MORE_LEFTOVER_GBP else "primary",
            )
        )

    # --- You: owe (all real debts on first paint) ---
    personal_owed: list[OverviewLine] = []
    mortgage_gbp = totals.mortgage_gbp
    # Prefer live register mortgage if totals somehow lag.
    if mortgage_gbp <= 0:
        mortgage_gbp = round(
            sum(
                d.balance_gbp
                for d in debt_list
                if d.scope == "personal" and d.debt_type == "mortgage" and d.balance_gbp > 0
            ),
            2,
        )
    if mortgage_configured or mortgage_gbp > 0:
        personal_owed.append(
            OverviewLine(
                "mortgage",
                "House mortgage",
                mortgage_gbp if mortgage_gbp > 0 else None,
                "debt",
                "primary",
                "Your half of the £164,421 joint mortgage" if mortgage_gbp > 0 else "",
            )
        )
    cards_gbp = totals.personal_credit_card_gbp
    personal_cards = [
        d
        for d in debt_list
        if d.scope == "personal" and d.debt_type == "credit_card" and d.balance_gbp > 0
    ]
    if cards_gbp <= 0:
        cards_gbp = round(sum(d.balance_gbp for d in personal_cards), 2)
    if cards_gbp > 0:
        personal_owed.append(
            OverviewLine(
                "personal_cards",
                "Credit cards",
                cards_gbp,
                "debt",
                "primary",
                _expensive_apr_hint(personal_cards),
            )
        )
    loans_gbp = totals.personal_loan_gbp
    personal_loans = [
        d
        for d in debt_list
        if d.scope == "personal"
        and d.debt_type in {"loan", "business_loan"}
        and d.balance_gbp > 0
    ]
    if loans_gbp <= 0:
        loans_gbp = round(sum(d.balance_gbp for d in personal_loans), 2)
    if loans_gbp > 0:
        personal_owed.append(
            OverviewLine(
                "personal_loans",
                "Loans",
                loans_gbp,
                "debt",
                "primary",
                _expensive_apr_hint(personal_loans),
            )
        )
    if totals.personal_overdraft_gbp > 0:
        personal_owed.append(
            OverviewLine(
                "personal_od",
                "Overdraft",
                totals.personal_overdraft_gbp,
                "debt",
                "primary",
            )
        )
    # Catch-all for personal register debts not already listed (never invent).
    covered = mortgage_gbp + cards_gbp + loans_gbp
    other_personal = round(max(totals.personal_debt_gbp - covered, 0.0), 2)
    if other_personal > 0.01:
        personal_owed.append(
            OverviewLine(
                "personal_other_debt",
                "Other amounts owed",
                other_personal,
                "debt",
                "primary",
            )
        )
    if director_owes_company > 0:
        personal_owed.append(
            OverviewLine(
                "robert_owes_company",
                "Robert still owes the company",
                director_owes_company,
                "debt",
                "primary",
            )
        )

    personal_owned_total = _sum_line_amounts(personal_owned)
    personal_owed_total = _sum_line_amounts(personal_owed)
    # Prefer the canonical personal_net_worth when it matches own−owe; else own−owe.
    personal_left = round(personal_owned_total - personal_owed_total, 2)
    if abs(personal_left - personal_whats_left) < 0.02:
        personal_left = personal_whats_left

    # --- Defence Legal ---
    bs = balance_sheet or {}
    fixed_assets = float(bs.get("fixed_assets_gbp") or 0.0)
    current_assets = float(bs.get("current_assets_gbp") or 0.0)
    current_liab = float(bs.get("current_liabilities_gbp") or 0.0)
    long_liab = float(bs.get("long_term_liabilities_gbp") or 0.0)
    capital = bs.get("capital_and_reserves_gbp")
    bs_present = capital is not None
    liability_lines = [
        line
        for line in list(bs.get("liability_lines") or [])
        if abs(float(line.get("amount_gbp") or 0)) > 0.005
    ]
    asset_lines = [
        line
        for line in list(bs.get("asset_lines") or [])
        if abs(float(line.get("amount_gbp") or 0)) > 0.005
    ]

    if bs_present:
        # Plain-English 1:1 of the stored QuickFile balance sheet.
        # Do not mix Lunch Flow / debt-register Tesla, cards, CoT, or loans.
        business_owned, business_owed, business_owned_total, business_owed_total, business_left = (
            _dls_from_quickfile_balance_sheet(
                fixed_assets=fixed_assets,
                current_assets=current_assets,
                current_liab=current_liab,
                long_liab=long_liab,
                capital=float(capital),
                asset_lines=asset_lines,
                liability_lines=liability_lines,
            )
        )
        business_hint = "From the Defence Legal balance sheet"
        business_available = True
    else:
        # Register / Lunch Flow fallback only when QuickFile BS is missing.
        vehicle_debts = [d for d in debt_list if _is_vehicle_hp_debt(d) and d.balance_gbp > 0]
        register_vehicle_hp = round(sum(d.balance_gbp for d in vehicle_debts), 2)
        tesla_hp_gbp = register_vehicle_hp

        business_owned = [
            OverviewLine("business_bank", "Bank", business_cash, "asset", "primary"),
        ]
        if totals.debtors_gbp > 0:
            business_owned.append(
                OverviewLine(
                    "customers_owe",
                    "Customers still to pay",
                    totals.debtors_gbp,
                    "asset",
                    "primary",
                )
            )
        if vehicle_debts or tesla_hp_gbp > 0:
            business_owned.append(
                OverviewLine(
                    "car_gap",
                    "Car value not on this list",
                    None,
                    "gap",
                    "primary",
                    "Finance is listed under what you owe, but the car itself is not counted here",
                )
            )
        for account in account_list:
            if (
                account.scope == "business"
                and account.account_type == "other_asset"
                and account.balance_gbp > 0
            ):
                business_owned.append(
                    OverviewLine(
                        f"biz_asset_{account.id}",
                        account.name,
                        account.balance_gbp,
                        "asset",
                        "primary",
                    )
                )
        if totals.vat_reserve_gbp != 0:
            business_owned.append(
                OverviewLine(
                    "vat_pot",
                    "VAT pot",
                    totals.vat_reserve_gbp,
                    "asset",
                    "more"
                    if abs(totals.vat_reserve_gbp) < _MORE_LEFTOVER_GBP
                    else "primary",
                )
            )
        if totals.corp_tax_reserve_gbp != 0:
            business_owned.append(
                OverviewLine(
                    "corp_tax_pot",
                    "Corporation tax set aside",
                    totals.corp_tax_reserve_gbp,
                    "asset",
                    "more"
                    if abs(totals.corp_tax_reserve_gbp) < _MORE_LEFTOVER_GBP
                    else "primary",
                )
            )
        if director_owes_company > 0:
            business_owned.append(
                OverviewLine(
                    "robert_owes_company_biz",
                    "Robert still owes the company",
                    director_owes_company,
                    "asset",
                    "primary",
                )
            )

        business_owed = []
        if totals.business_overdraft_gbp > 0:
            business_owed.append(
                OverviewLine(
                    "business_od",
                    "Overdraft",
                    totals.business_overdraft_gbp,
                    "debt",
                    "primary",
                )
            )
        if totals.business_credit_card_gbp > 0:
            business_owed.append(
                OverviewLine(
                    "business_cards",
                    "Credit cards",
                    totals.business_credit_card_gbp,
                    "debt",
                    "primary",
                )
            )
        if tesla_hp_gbp > 0:
            business_owed.append(
                OverviewLine(
                    f"vehicle_hp_{vehicle_debts[0].id}",
                    "Tesla still to pay",
                    tesla_hp_gbp,
                    "debt",
                    "primary",
                )
            )
        other_business_loans = round(
            max(totals.loan_gbp - register_vehicle_hp, 0.0),
            2,
        )
        if other_business_loans > 0:
            business_owed.append(
                OverviewLine(
                    "business_loans",
                    "Loans",
                    other_business_loans,
                    "debt",
                    "primary",
                )
            )
        if totals.creditors_gbp > 0:
            business_owed.append(
                OverviewLine(
                    "suppliers",
                    "Suppliers still to pay",
                    totals.creditors_gbp,
                    "debt",
                    "more"
                    if totals.creditors_gbp < _MORE_LEFTOVER_GBP
                    else "primary",
                )
            )
        if company_owes_director > 0:
            business_owed.append(
                OverviewLine(
                    "company_owes_robert_biz",
                    "Company still owes Robert",
                    company_owes_director,
                    "debt",
                    "primary",
                )
            )
        residual_register = round(
            max(
                totals.business_debt_gbp
                - totals.loan_gbp
                - totals.business_credit_card_gbp
                - (totals.creditors_gbp if totals.creditors_gbp > 0 else 0.0),
                0.0,
            ),
            2,
        )
        if residual_register > 0.01:
            business_owed.append(
                OverviewLine(
                    "business_other_debt",
                    "Other company debts",
                    residual_register,
                    "debt",
                    "primary",
                )
            )

        business_owned_total = _sum_line_amounts(business_owned)
        business_owed_total = _sum_line_amounts(business_owed)
        business_left = None
        business_hint = "Balance sheet not synced"
        business_available = False
        business_owned.insert(
            0,
            OverviewLine(
                "bs_missing",
                "Balance sheet not synced",
                None,
                "gap",
                "primary",
                "Connect QuickFile so What's left matches the company books",
            ),
        )

    personal = OverviewSideBreakdown(
        side="personal",
        owned_total_gbp=personal_owned_total,
        owed_total_gbp=personal_owed_total,
        whats_left_gbp=personal_left,
        owned=tuple(personal_owned),
        owed=tuple(personal_owed),
        whats_left_hint="",
        whats_left_available=True,
    )
    business = OverviewSideBreakdown(
        side="business",
        owned_total_gbp=business_owned_total,
        owed_total_gbp=business_owed_total,
        whats_left_gbp=business_left if business_available else None,
        owned=tuple(business_owned),
        owed=tuple(business_owed),
        whats_left_hint=business_hint,
        whats_left_available=business_available,
    )
    return personal, business


def overview_side_to_dict(side: OverviewSideBreakdown) -> dict:
    return {
        "side": side.side,
        "owned_total_gbp": side.owned_total_gbp,
        "owed_total_gbp": side.owed_total_gbp,
        "whats_left_gbp": side.whats_left_gbp,
        "whats_left_hint": side.whats_left_hint,
        "whats_left_available": side.whats_left_available,
        "owned": [
            {
                "key": line.key,
                "label": line.label,
                "amount_gbp": line.amount_gbp,
                "kind": line.kind,
                "tier": line.tier,
                "hint": line.hint,
            }
            for line in side.owned
        ],
        "owed": [
            {
                "key": line.key,
                "label": line.label,
                "amount_gbp": line.amount_gbp,
                "kind": line.kind,
                "tier": line.tier,
                "hint": line.hint,
            }
            for line in side.owed
        ],
    }


def external_debt_gbp(
    personal_debt: float,
    business_debt: float,
    directors_loan: float = 0.0,
    *,
    personal_overdraft: float = 0.0,
    business_overdraft: float = 0.0,
) -> float:
    """Third-party debt owed (register + overdrafts). Excludes director's loan.

    Overdrafts are included so the combined figure matches the personal and
    business debt stacks a reader sees on Overview (bank tiles stay net).
    """
    del directors_loan
    return round(
        max(
            personal_debt + business_debt + personal_overdraft + business_overdraft,
            0.0,
        ),
        2,
    )


def sanitize_mortgage_original_balance(
    debt_type: str,
    original_balance_gbp: float | None,
) -> float | None:
    """Never present the stale £175k mortgage placeholder as a real original."""
    # Confirmed half-share of £164,421 joint — keep in sync with finance_seed_service.
    stale_original = 175000.0
    confirmed_half = 82210.50
    if debt_type != "mortgage" or original_balance_gbp is None:
        return original_balance_gbp
    if abs(float(original_balance_gbp) - stale_original) < 0.01:
        return confirmed_half
    return original_balance_gbp


def build_finance_data_gaps(
    liabilities: Iterable[LiabilityView],
    *,
    monthly_income_gbp: float,
    monthly_spending_gbp: float,
    monthly_flow_source: str,
    budget_income_gbp: float | None,
    monthly_interest_incomplete: bool,
) -> dict[str, object]:
    """Call out missing APR / limits / incomplete interest / thin income."""
    unknown_apr_names: list[str] = []
    missing_limit_names: list[str] = []
    for debt in _active_debts(liabilities):
        if not is_repayable_debt(debt):
            continue
        if not debt.interest_rate_known:
            unknown_apr_names.append(debt.name)
        if debt.debt_type in {"credit_card", "business_loan"} and (
            debt.credit_limit_gbp is None or debt.credit_limit_gbp <= 0
        ):
            missing_limit_names.append(debt.name)

    income_looks_thin = False
    income_thin_note = ""
    income = float(monthly_income_gbp or 0.0)
    spending = float(monthly_spending_gbp or 0.0)
    budget_income = float(budget_income_gbp or 0.0)
    if income > 0:
        if budget_income >= 1500 and income < budget_income * 0.4:
            income_looks_thin = True
            income_thin_note = (
                f"Recorded month income {income:.0f} looks low vs typical budget "
                f"income {budget_income:.0f} — check transfers / period coverage."
            )
        elif (
            monthly_flow_source == "open_banking"
            and spending > 0
            and income < spending * 0.35
        ):
            income_looks_thin = True
            income_thin_note = (
                "Open Banking month income looks thin vs spending — salary may "
                "not have posted in this window yet."
            )
        elif income < 500 and spending >= 1500:
            income_looks_thin = True
            income_thin_note = (
                "Month income looks implausibly low against spending — verify "
                "the income source before trusting surplus."
            )

    return {
        "unknown_apr_count": len(unknown_apr_names),
        "unknown_apr_names": unknown_apr_names,
        "missing_credit_limit_count": len(missing_limit_names),
        "missing_credit_limit_names": missing_limit_names,
        "monthly_interest_incomplete": bool(monthly_interest_incomplete),
        "income_looks_thin": income_looks_thin,
        "income_thin_note": income_thin_note,
    }


def monthly_interest_from_debts(
    liabilities: Iterable[LiabilityView],
) -> tuple[float, bool]:
    """Sum monthly interest from repayable debts with known APR.

    Director's loan is excluded (internal, not third-party interest).
    Returns (total, incomplete) where incomplete means at least one repayable
    debt is missing APR. The total still includes every debt that does have
    APR so Overview can show a partial forecast instead of blanking the tile.
    """
    total = 0.0
    missing = 0
    for item in _active_debts(liabilities):
        if not is_repayable_debt(item):
            continue
        if not item.interest_rate_known:
            missing += 1
            continue
        total += monthly_interest_gbp(item.balance_gbp, item.interest_rate_pct)
    return round(total, 2), missing > 0


def high_interest_debt_gbp(
    liabilities: Iterable[LiabilityView],
    *,
    threshold_pct: float = 15.0,
) -> float:
    total = 0.0
    for item in _active_debts(liabilities):
        if not is_repayable_debt(item):
            continue
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
    if cashflow_income > 0 or cashflow_spending > 0 or cashflow_bills > 0:
        return (
            round(cashflow_income, 2),
            round(cashflow_spending, 2),
            round(cashflow_bills, 2),
            round(snapshot_repayments, 2) if snapshot_present else 0.0,
            "cashflow",
            True,
        )
    # Prefer the typical budget plan over a thin Open Banking 30-day window so
    # salary that has not yet posted this month is not treated as £0 income.
    if budget_income > 0 or budget_spending > 0:
        return (
            round(budget_income, 2),
            round(budget_spending, 2),
            0.0,
            round(snapshot_repayments, 2) if snapshot_present else 0.0,
            "budget",
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
