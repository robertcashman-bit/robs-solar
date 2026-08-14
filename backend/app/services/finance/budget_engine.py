"""Deterministic budget planning engine.

All arithmetic for suggested budgets, totals, and variance lives here.
UI and other services must call these functions rather than re-implementing them.
Unknown amounts stay None — they are never coerced to zero.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Literal

BudgetStrategy = Literal["stabilise", "balanced", "debt_attack", "custom"]
BudgetView = Literal["personal", "business", "consolidated"]
BudgetItemKind = Literal[
    "income",
    "essential",
    "debt_minimum",
    "debt_overpayment",
    "tax_provision",
    "buffer",
    "discretionary",
    "other",
]
PaymentFrequency = Literal["weekly", "fortnightly", "four_weekly", "monthly", "annual"]

TWOPLACE = Decimal("0.01")
ZERO = Decimal("0")

FREQUENCY_TO_MONTHLY: dict[str, Decimal] = {
    "weekly": Decimal("52") / Decimal("12"),
    "fortnightly": Decimal("26") / Decimal("12"),
    "four_weekly": Decimal("13") / Decimal("12"),
    "monthly": Decimal("1"),
    "annual": Decimal("1") / Decimal("12"),
}

OUTFLOW_KINDS: frozenset[str] = frozenset(
    {
        "essential",
        "debt_minimum",
        "debt_overpayment",
        "tax_provision",
        "buffer",
        "discretionary",
        "other",
    }
)

MANDATORY_KINDS: frozenset[str] = frozenset(
    {"essential", "debt_minimum", "tax_provision"}
)

TRANSFER_DEBT_TYPES: frozenset[str] = frozenset({"directors_loan"})
TRANSFER_ACCOUNT_TYPES: frozenset[str] = frozenset({"directors_loan"})
DEBT_ACCOUNT_TYPES: frozenset[str] = frozenset(
    {"credit_card", "loan", "mortgage", "capital_on_tap", "creditors"}
)

# Shares of genuinely unallocated surplus. Not invented household figures.
STRATEGY_SURPLUS_SPLIT: dict[str, dict[str, Decimal]] = {
    "stabilise": {
        "buffer": Decimal("0.50"),
        "overpayment": Decimal("0.15"),
        "discretionary": Decimal("0.25"),
        "surplus": Decimal("0.10"),
    },
    "balanced": {
        "buffer": Decimal("0.25"),
        "overpayment": Decimal("0.35"),
        "discretionary": Decimal("0.40"),
        "surplus": Decimal("0.00"),
    },
    "debt_attack": {
        "buffer": Decimal("0.15"),
        "overpayment": Decimal("0.65"),
        "discretionary": Decimal("0.20"),
        "surplus": Decimal("0.00"),
    },
}

SOURCE_LABELS: dict[str, str] = {
    "snapshot": "From active income record",
    "quickfile": "From QuickFile P&L",
    "liability": "From debt record",
    "account": "From account record",
    "cashflow": "From confirmed cash-flow entry",
    "transaction_average": "From average actual spend",
    "tax_liability": "From tax liability",
    "generated": "Allocated from available surplus",
    "user_entered": "User entered",
    "user_override": "User override",
}


def to_decimal(value: float | int | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def money(value: Decimal) -> float:
    """Round half-up to 2 decimal places once, at a display/persist boundary."""
    return float(value.quantize(TWOPLACE, rounding=ROUND_HALF_UP))


def to_monthly_amount(
    amount: float | int | Decimal,
    frequency: PaymentFrequency | str,
) -> Decimal:
    """Convert a known amount at `frequency` into a monthly equivalent."""
    key = str(frequency).strip().lower()
    if key not in FREQUENCY_TO_MONTHLY:
        raise ValueError(f"Unsupported payment frequency: {frequency}")
    return Decimal(str(amount)) * FREQUENCY_TO_MONTHLY[key]


def parse_budget_amount(raw: str | None) -> Decimal | None:
    """Parse a user-entered amount. Blank is missing (None), not zero."""
    if raw is None:
        return None
    trimmed = raw.strip()
    if not trimmed:
        return None
    cleaned = re.sub(r"[£$,]", "", trimmed)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except Exception as exc:
        raise ValueError("Amount must be a number. Blank values are not saved as zero.") from exc


def item_key(
    *,
    scope: str,
    kind: str,
    source_record_type: str | None,
    source_record_id: int | None,
    slug: str,
) -> str:
    record_type = source_record_type or "none"
    record_id = source_record_id if source_record_id is not None else 0
    safe_slug = re.sub(r"[^a-z0-9]+", "-", slug.lower()).strip("-") or "item"
    return f"{scope}:{kind}:{record_type}:{record_id}:{safe_slug}"


@dataclass
class BudgetDraftItem:
    key: str
    scope: str
    kind: str
    category: str
    amount_gbp: float | None
    source: str
    source_label: str
    source_record_type: str | None = None
    source_record_id: int | None = None
    is_generated: bool = True
    is_user_override: bool = False
    is_transfer: bool = False
    is_missing: bool = False
    notes: str = ""
    record_href: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MissingInput:
    code: str
    message: str
    record_href: str | None = None
    source_record_type: str | None = None
    source_record_id: int | None = None
    category: str | None = None


@dataclass
class TaxContext:
    vat_reserved_gbp: float | None = None
    corp_tax_reserved_gbp: float | None = None
    vat_due_gbp: float | None = None
    notes: list[str] = field(default_factory=list)


@dataclass
class CashContext:
    savings_balance_gbp: float | None = None
    savings_accounts_found: bool = False


@dataclass
class BudgetInputs:
    items: list[BudgetDraftItem]
    missing: list[MissingInput]
    notes: list[str]
    fingerprint: str
    tax: TaxContext
    cash: CashContext
    highest_apr_debt_name: str | None = None
    highest_apr_debt_id: int | None = None
    highest_apr_pct: float | None = None
    overpayment_basis: str = "none"
    discretionary_reference_gbp: float | None = None
    discretionary_categories: list[tuple[str, Decimal]] = field(default_factory=list)


@dataclass
class BudgetTotals:
    view: str
    income_gbp: float
    essential_gbp: float
    debt_minimum_gbp: float
    debt_overpayment_gbp: float
    tax_provision_gbp: float
    buffer_gbp: float
    discretionary_gbp: float
    other_gbp: float
    committed_gbp: float
    allocated_gbp: float
    surplus_gbp: float | None
    income_complete: bool
    has_missing_inputs: bool
    is_deficit: bool
    incomplete_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BudgetDraft:
    strategy: str
    name: str
    items: list[BudgetDraftItem]
    missing: list[MissingInput]
    notes: list[str]
    fingerprint: str
    tax: TaxContext
    cash: CashContext
    totals_personal: BudgetTotals
    totals_business: BudgetTotals
    totals_consolidated: BudgetTotals
    recommended: bool = False


@dataclass
class VarianceLine:
    category: str
    kind: str
    scope: str
    budgeted_gbp: float | None
    actual_gbp: float | None
    variance_gbp: float | None
    is_missing: bool = False
    matched: bool = False


@dataclass
class BudgetVariance:
    available: bool
    reason: str
    month: str
    view: str
    lines: list[VarianceLine]
    unbudgeted_actuals: list[VarianceLine]
    budgeted_total_gbp: float
    actual_total_gbp: float


@dataclass
class PersonalSnapshotInput:
    exists: bool
    snapshot_id: int | None = None
    monthly_income_gbp: float = 0.0
    household_bills_gbp: float = 0.0
    monthly_spending_gbp: float = 0.0
    debt_repayments_gbp: float = 0.0


@dataclass
class BusinessSnapshotInput:
    exists: bool
    source: str = "snapshot"
    snapshot_id: int | None = None
    turnover_gbp: float = 0.0
    expenses_gbp: float = 0.0
    vat_reserve_gbp: float = 0.0
    corp_tax_reserve_gbp: float = 0.0


@dataclass
class DebtRecordInput:
    id: int
    scope: str
    name: str
    debt_type: str
    balance_gbp: float
    interest_rate_pct: float
    minimum_payment_gbp: float | None
    overpayment_gbp: float = 0.0
    account_id: int | None = None
    origin: str = "liability"


@dataclass
class CashflowRecordInput:
    id: int
    scope: str
    entry_type: str
    label: str
    amount_gbp: float
    is_confirmed: bool = True


@dataclass
class TransactionAverageInput:
    category: str
    monthly_average_gbp: float
    scope: str = "personal"


def source_fingerprint(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def _source_label(source: str) -> str:
    return SOURCE_LABELS.get(source, source.replace("_", " ").title())


def _make_item(
    *,
    scope: str,
    kind: str,
    category: str,
    amount: Decimal | float | None,
    source: str,
    source_record_type: str | None = None,
    source_record_id: int | None = None,
    is_generated: bool = True,
    is_user_override: bool = False,
    is_transfer: bool = False,
    is_missing: bool = False,
    notes: str = "",
    record_href: str | None = None,
    slug: str | None = None,
) -> BudgetDraftItem:
    amount_gbp: float | None
    if amount is None or is_missing:
        amount_gbp = None
        is_missing = True
    else:
        amount_gbp = money(amount if isinstance(amount, Decimal) else Decimal(str(amount)))
    return BudgetDraftItem(
        key=item_key(
            scope=scope,
            kind=kind,
            source_record_type=source_record_type,
            source_record_id=source_record_id,
            slug=slug or category,
        ),
        scope=scope,
        kind=kind,
        category=category,
        amount_gbp=amount_gbp,
        source=source,
        source_label=_source_label(source),
        source_record_type=source_record_type,
        source_record_id=source_record_id,
        is_generated=is_generated,
        is_user_override=is_user_override,
        is_transfer=is_transfer,
        is_missing=is_missing,
        notes=notes,
        record_href=record_href,
    )


def calculate_budget_inputs(
    *,
    personal: PersonalSnapshotInput | None,
    business: BusinessSnapshotInput | None,
    debts: Iterable[DebtRecordInput],
    confirmed_cashflow: Iterable[CashflowRecordInput] = (),
    transaction_averages: Iterable[TransactionAverageInput] = (),
    savings_balance_gbp: float | None = None,
    savings_accounts_found: bool = False,
    vat_due_gbp: float | None = None,
    account_vat_reserve_gbp: float = 0.0,
    account_corp_tax_reserve_gbp: float = 0.0,
    skipped_inactive_debts: Iterable[DebtRecordInput] = (),
    extra_notes: Iterable[str] = (),
) -> BudgetInputs:
    """Derive budget source items from persisted financial records only."""
    items: list[BudgetDraftItem] = []
    missing: list[MissingInput] = []
    notes: list[str] = list(extra_notes)
    debt_list = [d for d in debts if d.balance_gbp > 0]
    for skipped in skipped_inactive_debts:
        if skipped.balance_gbp <= 0:
            continue
        missing.append(
            MissingInput(
                code="inactive_debt",
                message=(
                    f"{skipped.name} has a remaining balance but is marked inactive, "
                    "so it is not included. Activate it on Debts if it belongs in this budget."
                ),
                record_href="/finance/debts",
                source_record_type="liability",
                source_record_id=skipped.id,
                category=skipped.name,
            )
        )
    cashflow_list = [c for c in confirmed_cashflow if c.is_confirmed]
    averages = list(transaction_averages)

    fingerprint_payload: dict[str, Any] = {
        "personal": None,
        "business": None,
        "debts": [],
        "cashflow": [],
        "averages": [],
        "savings": savings_balance_gbp if savings_accounts_found else None,
        "vat_due": vat_due_gbp,
    }

    if personal is None or not personal.exists:
        missing.append(
            MissingInput(
                code="personal_income",
                message="No personal income snapshot on file. Monthly income needs input.",
                record_href="/finance/personal",
                source_record_type="snapshot",
            )
        )
        missing.append(
            MissingInput(
                code="household_bills",
                message="Regular household bills amount is unavailable.",
                record_href="/finance/personal",
                source_record_type="snapshot",
            )
        )
        items.append(
            _make_item(
                scope="personal",
                kind="income",
                category="Personal income",
                amount=None,
                source="snapshot",
                is_missing=True,
                notes=(
                    "No personal income snapshot on file. "
                    "Enter a monthly figure here or add one on Personal."
                ),
                record_href="/finance/personal",
            )
        )
        items.append(
            _make_item(
                scope="personal",
                kind="essential",
                category="Household bills",
                amount=None,
                source="snapshot",
                is_missing=True,
                notes="Household bills amount is unavailable. Enter it here or on Personal.",
                record_href="/finance/personal",
            )
        )
    else:
        fingerprint_payload["personal"] = {
            "id": personal.snapshot_id,
            "income": personal.monthly_income_gbp,
            "bills": personal.household_bills_gbp,
            "spending": personal.monthly_spending_gbp,
            "debt_repay": personal.debt_repayments_gbp,
        }
        items.append(
            _make_item(
                scope="personal",
                kind="income",
                category="Personal income",
                amount=personal.monthly_income_gbp,
                source="snapshot",
                source_record_type="snapshot",
                source_record_id=personal.snapshot_id,
                notes="From the latest personal finance snapshot.",
                record_href="/finance/personal",
            )
        )
        items.append(
            _make_item(
                scope="personal",
                kind="essential",
                category="Household bills",
                amount=personal.household_bills_gbp,
                source="snapshot",
                source_record_type="snapshot",
                source_record_id=personal.snapshot_id,
                notes="Recorded household bills. Not classified beyond the snapshot field.",
                record_href="/finance/personal",
            )
        )

    if business is None or not business.exists:
        missing.append(
            MissingInput(
                code="business_income",
                message="No business turnover on file (QuickFile P&L or business snapshot).",
                record_href="/finance/business",
                source_record_type="snapshot",
            )
        )
        # Do not add a £0/missing business income line when no business record
        # exists — that would make a personal-only surplus look incomplete.
    else:
        fingerprint_payload["business"] = {
            "id": business.snapshot_id,
            "source": business.source,
            "turnover": business.turnover_gbp,
            "expenses": business.expenses_gbp,
            "vat": business.vat_reserve_gbp,
            "corp": business.corp_tax_reserve_gbp,
        }
        source = "quickfile" if business.source == "quickfile" else "snapshot"
        items.append(
            _make_item(
                scope="business",
                kind="income",
                category="Business turnover",
                amount=business.turnover_gbp,
                source=source,
                source_record_type="snapshot" if source == "snapshot" else "quickfile",
                source_record_id=business.snapshot_id,
                notes=(
                    "From QuickFile profit and loss."
                    if source == "quickfile"
                    else "From the latest business finance snapshot."
                ),
                record_href="/finance/business",
            )
        )
        items.append(
            _make_item(
                scope="business",
                kind="essential",
                category="Business expenses",
                amount=business.expenses_gbp,
                source=source,
                source_record_type="snapshot" if source == "snapshot" else "quickfile",
                source_record_id=business.snapshot_id,
                notes=(
                    "Recorded business expenses. May include salary or drawings paid to you. "
                    "Mark those as transfers in a custom budget if they also "
                    "appear as personal income."
                ),
                record_href="/finance/business",
            )
        )
        notes.append(
            "Business expenses and personal income are kept separate. "
            "In the consolidated view, mark salary, dividends, or Director's Loan movements "
            "as transfers so they are not counted twice."
        )

    for debt in debt_list:
        fingerprint_payload["debts"].append(
            {
                "id": debt.id,
                "origin": debt.origin,
                "min": debt.minimum_payment_gbp,
                "over": debt.overpayment_gbp,
                "balance": debt.balance_gbp,
                "rate": debt.interest_rate_pct,
            }
        )
        is_transfer = debt.debt_type in TRANSFER_DEBT_TYPES
        href = "/finance/debts" if debt.origin == "liability" else "/finance/personal"
        min_known = debt.minimum_payment_gbp is not None
        if not min_known:
            missing.append(
                MissingInput(
                    code="debt_minimum",
                    message=f"Monthly payment missing for {debt.name}.",
                    record_href=href,
                    source_record_type=debt.origin,
                    source_record_id=debt.id,
                    category=debt.name,
                )
            )
        items.append(
            _make_item(
                scope=debt.scope,
                kind="debt_minimum",
                category=f"Debt minimum — {debt.name}",
                amount=debt.minimum_payment_gbp if min_known else None,
                source=debt.origin,
                source_record_type=debt.origin,
                source_record_id=debt.id,
                is_missing=not min_known,
                is_transfer=is_transfer,
                notes=(
                    "Director's Loan movement — treated as a transfer in the consolidated view."
                    if is_transfer
                    else f"Required/minimum payment on record. Balance {debt.balance_gbp}."
                ),
                record_href=href,
                slug=debt.name,
            )
        )
        if debt.overpayment_gbp and debt.overpayment_gbp > 0:
            items.append(
                _make_item(
                    scope=debt.scope,
                    kind="debt_overpayment",
                    category=f"Recorded overpayment — {debt.name}",
                    amount=debt.overpayment_gbp,
                    source=debt.origin,
                    source_record_type=debt.origin,
                    source_record_id=debt.id,
                    is_transfer=is_transfer,
                    notes="Regular extra payment already stored on the debt record.",
                    record_href=href,
                    slug=f"{debt.name}-over",
                )
            )
    payable_debts = [
        d
        for d in debt_list
        if d.minimum_payment_gbp is not None and d.debt_type not in TRANSFER_DEBT_TYPES
    ]
    apr_ranked = [d for d in payable_debts if d.interest_rate_pct and d.interest_rate_pct > 0]
    overpayment_basis = "none"
    highest_apr_name: str | None = None
    highest_apr_id: int | None = None
    highest_apr_pct: float | None = None
    if apr_ranked:
        target = max(apr_ranked, key=lambda d: d.interest_rate_pct)
        highest_apr_name = target.name
        highest_apr_id = target.id
        highest_apr_pct = target.interest_rate_pct
        overpayment_basis = "apr"
    elif payable_debts:
        target = max(payable_debts, key=lambda d: d.balance_gbp)
        highest_apr_name = target.name
        highest_apr_id = target.id
        overpayment_basis = "largest_balance"

    # Snapshot debt_repayments only when no liability records exist (avoid double count).
    has_personal_debt_items = any(
        i.kind == "debt_minimum" and i.scope == "personal" for i in items
    )
    if (
        personal
        and personal.exists
        and personal.debt_repayments_gbp
        and personal.debt_repayments_gbp > 0
        and not has_personal_debt_items
    ):
        items.append(
            _make_item(
                scope="personal",
                kind="debt_minimum",
                category="Debt repayments (snapshot)",
                amount=personal.debt_repayments_gbp,
                source="snapshot",
                source_record_type="snapshot",
                source_record_id=personal.snapshot_id,
                notes="From the personal snapshot. No individual debt records were available.",
                record_href="/finance/personal",
            )
        )

    covered_cashflow_labels: set[str] = set()
    for entry in cashflow_list:
        fingerprint_payload["cashflow"].append(
            {"id": entry.id, "type": entry.entry_type, "amount": entry.amount_gbp}
        )
        label_key = entry.label.strip().lower()
        if label_key in covered_cashflow_labels:
            continue
        covered_cashflow_labels.add(label_key)
        amount = abs(Decimal(str(entry.amount_gbp)))
        is_income_entry = entry.entry_type == "income" or (
            entry.amount_gbp > 0 and entry.entry_type not in {"tax_vat", "bill", "debt"}
        )
        if is_income_entry:
            if any(i.kind == "income" and i.scope == entry.scope for i in items):
                continue
            items.append(
                _make_item(
                    scope=entry.scope,
                    kind="income",
                    category=entry.label,
                    amount=amount,
                    source="cashflow",
                    source_record_type="cashflow",
                    source_record_id=entry.id,
                    notes="From a confirmed cash-flow income entry.",
                    record_href="/finance/cash-flow",
                )
            )
            continue
        if entry.entry_type == "bill":
            items.append(
                _make_item(
                    scope=entry.scope,
                    kind="essential",
                    category=entry.label,
                    amount=amount,
                    source="cashflow",
                    source_record_type="cashflow",
                    source_record_id=entry.id,
                    notes="From a confirmed cash-flow bill.",
                    record_href="/finance/cash-flow",
                )
            )
        elif entry.entry_type == "tax_vat":
            items.append(
                _make_item(
                    scope=entry.scope,
                    kind="tax_provision",
                    category=entry.label,
                    amount=amount,
                    source="cashflow",
                    source_record_type="cashflow",
                    source_record_id=entry.id,
                    notes=(
                        "Monthly tax provision from a confirmed cash-flow entry. "
                        "Not an estimate."
                    ),
                    record_href="/finance/cash-flow",
                )
            )
        elif entry.entry_type == "debt":
            # Avoid duplicating liability-derived minimums.
            if any(i.kind == "debt_minimum" and i.scope == entry.scope for i in items):
                continue
            items.append(
                _make_item(
                    scope=entry.scope,
                    kind="debt_minimum",
                    category=entry.label,
                    amount=amount,
                    source="cashflow",
                    source_record_type="cashflow",
                    source_record_id=entry.id,
                    notes="From a confirmed cash-flow debt entry.",
                    record_href="/finance/cash-flow",
                )
            )
        elif entry.entry_type == "other" and entry.amount_gbp < 0:
            items.append(
                _make_item(
                    scope=entry.scope,
                    kind="other",
                    category=entry.label,
                    amount=amount,
                    source="cashflow",
                    source_record_type="cashflow",
                    source_record_id=entry.id,
                    notes="From a confirmed cash-flow entry.",
                    record_href="/finance/cash-flow",
                )
            )

    vat_reserved = None
    corp_reserved = None
    tax_notes: list[str] = []
    if business and business.exists:
        if business.vat_reserve_gbp or account_vat_reserve_gbp:
            vat_reserved = max(business.vat_reserve_gbp, account_vat_reserve_gbp)
        if business.corp_tax_reserve_gbp or account_corp_tax_reserve_gbp:
            corp_reserved = max(business.corp_tax_reserve_gbp, account_corp_tax_reserve_gbp)
    else:
        if account_vat_reserve_gbp:
            vat_reserved = account_vat_reserve_gbp
        if account_corp_tax_reserve_gbp:
            corp_reserved = account_corp_tax_reserve_gbp

    if vat_reserved is not None:
        tax_notes.append(
            f"VAT reserved (existing cash, not a monthly provision): £{vat_reserved:,.2f}."
        )
    if corp_reserved is not None:
        tax_notes.append(
            "Corporation tax reserved (existing cash, not a monthly provision): "
            f"£{corp_reserved:,.2f}."
        )
    if vat_due_gbp is not None:
        tax_notes.append(
            f"VAT amount due on file: £{vat_due_gbp:,.2f}. "
            "This is a liability balance, not a monthly budget provision."
        )
    has_tax_provision = any(i.kind == "tax_provision" for i in items)
    if (vat_reserved or corp_reserved or vat_due_gbp) and not has_tax_provision:
        missing.append(
            MissingInput(
                code="tax_provision",
                message=(
                    "Monthly tax provision needs input. Reserved balances and amounts due "
                    "are shown separately and are not treated as a monthly figure."
                ),
                record_href="/finance/business",
                source_record_type="tax",
            )
        )
        items.append(
            _make_item(
                scope="business",
                kind="tax_provision",
                category="Monthly tax provision",
                amount=None,
                source="tax_liability",
                is_missing=True,
                notes=(
                    "Enter a monthly VAT / corporation-tax provision. "
                    "Existing reserves are not guessed as a monthly amount."
                ),
                record_href="/finance/business",
            )
        )

    discretionary_reference: float | None = None
    discretionary_categories: list[tuple[str, Decimal]] = []
    if personal and personal.exists:
        discretionary_reference = personal.monthly_spending_gbp
    if averages:
        fingerprint_payload["averages"] = [
            {"category": a.category, "avg": a.monthly_average_gbp, "scope": a.scope}
            for a in averages
        ]
        if discretionary_reference is None:
            total_avg = sum((Decimal(str(a.monthly_average_gbp)) for a in averages), ZERO)
            discretionary_reference = money(total_avg)
            discretionary_categories = [
                (a.category, Decimal(str(a.monthly_average_gbp))) for a in averages
            ]
        else:
            notes.append(
                "Transaction category averages exist but were not added as extra lines "
                "because personal snapshot spending is already on file (avoids double-counting)."
            )

    cash = CashContext(
        savings_balance_gbp=savings_balance_gbp if savings_accounts_found else None,
        savings_accounts_found=savings_accounts_found,
    )
    if savings_accounts_found and savings_balance_gbp is not None:
        notes.append(
            f"Existing savings / buffer cash on file: £{savings_balance_gbp:,.2f}. "
            "This is a balance, not the monthly contribution."
        )
    elif not savings_accounts_found:
        notes.append(
            "No savings account on file. Existing cash buffer is unknown, "
            "not assumed to be zero."
        )

    return BudgetInputs(
        items=items,
        missing=missing,
        notes=notes + tax_notes,
        fingerprint=source_fingerprint(fingerprint_payload),
        tax=TaxContext(
            vat_reserved_gbp=vat_reserved,
            corp_tax_reserved_gbp=corp_reserved,
            vat_due_gbp=vat_due_gbp,
            notes=tax_notes,
        ),
        cash=cash,
        highest_apr_debt_name=highest_apr_name,
        highest_apr_debt_id=highest_apr_id,
        highest_apr_pct=highest_apr_pct,
        overpayment_basis=overpayment_basis,
        discretionary_reference_gbp=discretionary_reference,
        discretionary_categories=discretionary_categories,
    )


def _item_amount(item: BudgetDraftItem) -> Decimal:
    if item.amount_gbp is None:
        return ZERO
    return Decimal(str(item.amount_gbp))


def _visible_items(items: Iterable[BudgetDraftItem], view: BudgetView) -> list[BudgetDraftItem]:
    selected: list[BudgetDraftItem] = []
    for item in items:
        if view == "consolidated":
            if item.is_transfer:
                continue
            selected.append(item)
        elif item.scope == view:
            selected.append(item)
    return selected


def calculate_budget_totals(
    items: Iterable[BudgetDraftItem],
    view: BudgetView = "consolidated",
) -> BudgetTotals:
    selected = _visible_items(items, view)
    income_items = [i for i in selected if i.kind == "income"]
    income_complete = bool(income_items) and all(
        not i.is_missing and i.amount_gbp is not None for i in income_items
    )

    def sum_kind(kind: str) -> Decimal:
        return sum(
            (_item_amount(i) for i in selected if i.kind == kind and not i.is_missing),
            ZERO,
        )

    income = sum_kind("income")
    essential = sum_kind("essential")
    debt_min = sum_kind("debt_minimum")
    debt_over = sum_kind("debt_overpayment")
    tax = sum_kind("tax_provision")
    buffer = sum_kind("buffer")
    discretionary = sum_kind("discretionary")
    other = sum_kind("other")
    committed = essential + debt_min + tax
    allocated = essential + debt_min + debt_over + tax + buffer + discretionary + other
    surplus: float | None
    incomplete_reason = ""
    if not income_complete:
        surplus = None
        incomplete_reason = "Projected surplus unavailable — monthly income needs input."
    else:
        surplus = money(income - allocated)

    material_missing = any(
        i.is_missing and i.kind in {"income", "essential", "debt_minimum", "tax_provision"}
        for i in selected
    )
    is_deficit = surplus is not None and surplus < 0

    return BudgetTotals(
        view=view,
        income_gbp=money(income),
        essential_gbp=money(essential),
        debt_minimum_gbp=money(debt_min),
        debt_overpayment_gbp=money(debt_over),
        tax_provision_gbp=money(tax),
        buffer_gbp=money(buffer),
        discretionary_gbp=money(discretionary),
        other_gbp=money(other),
        committed_gbp=money(committed),
        allocated_gbp=money(allocated),
        surplus_gbp=surplus,
        income_complete=income_complete,
        has_missing_inputs=material_missing,
        is_deficit=is_deficit,
        incomplete_reason=incomplete_reason,
    )


def calculate_mandatory_commitments(
    items: Iterable[BudgetDraftItem],
    view: BudgetView = "consolidated",
) -> Decimal:
    selected = _visible_items(items, view)
    return sum(
        (
            _item_amount(i)
            for i in selected
            if i.kind in MANDATORY_KINDS and not i.is_missing
        ),
        ZERO,
    )


def _unallocated_surplus(inputs: BudgetInputs) -> Decimal | None:
    totals = calculate_budget_totals(inputs.items, "consolidated")
    if not totals.income_complete:
        return None
    # Unallocated = income − mandatory − recorded overpayments (before strategy extras).
    income = Decimal(str(totals.income_gbp))
    mandatory = Decimal(str(totals.committed_gbp))
    recorded_over = Decimal(str(totals.debt_overpayment_gbp))
    other = Decimal(str(totals.other_gbp))
    return income - mandatory - recorded_over - other


def _distribute_discretionary(
    total: Decimal,
    categories: list[tuple[str, Decimal]],
) -> list[tuple[str, Decimal]]:
    if not categories or total <= ZERO:
        return []
    weight = sum((value for _, value in categories), ZERO)
    if weight <= ZERO:
        return []
    allocated: list[tuple[str, Decimal]] = []
    remaining = total
    for index, (name, value) in enumerate(categories):
        if index == len(categories) - 1:
            share = remaining
        else:
            share = (total * value / weight).quantize(TWOPLACE, rounding=ROUND_HALF_UP)
            remaining -= share
        allocated.append((name, share))
    return allocated


def generate_suggested_budget(
    inputs: BudgetInputs,
    strategy: BudgetStrategy,
) -> BudgetDraft:
    """Allocate known surplus according to a named strategy. Does not invent income."""
    if strategy == "custom":
        base_strategy: BudgetStrategy = "balanced"
    else:
        base_strategy = strategy

    items = [BudgetDraftItem(**asdict(item)) for item in inputs.items]
    missing = list(inputs.missing)
    notes = list(inputs.notes)
    unallocated = _unallocated_surplus(inputs)

    names = {
        "stabilise": "Stabilise",
        "balanced": "Balanced",
        "debt_attack": "Debt Attack",
        "custom": "Custom",
    }

    if unallocated is None:
        notes.append(
            "Income is missing, so surplus cannot be split across buffer, "
            "discretionary, or extra debt payments."
        )
    elif unallocated <= ZERO:
        notes.append(
            "No unallocated surplus after required commitments. "
            "Extra buffer, discretionary, and debt overpayment were not invented."
        )
        if unallocated < ZERO:
            notes.append(
                f"Known commitments exceed known income by £{money(-unallocated):,.2f}."
            )
    else:
        split = STRATEGY_SURPLUS_SPLIT[base_strategy]
        buffer_amt = (unallocated * split["buffer"]).quantize(TWOPLACE, rounding=ROUND_HALF_UP)
        over_amt = (unallocated * split["overpayment"]).quantize(TWOPLACE, rounding=ROUND_HALF_UP)
        disc_amt = (unallocated * split["discretionary"]).quantize(TWOPLACE, rounding=ROUND_HALF_UP)

        items.append(
            _make_item(
                scope="personal",
                kind="buffer",
                category="Cash buffer contribution",
                amount=buffer_amt,
                source="generated",
                notes=(
                    f"{base_strategy.replace('_', ' ').title()} share of available surplus. "
                    "Existing savings balances are shown separately and are not this contribution."
                ),
                slug="cash-buffer",
            )
        )

        if over_amt > ZERO:
            if inputs.highest_apr_debt_name and inputs.highest_apr_debt_id is not None:
                label = (
                    f"Additional debt repayment — {inputs.highest_apr_debt_name}"
                )
                extra_notes = (
                    (
                        f"Planning allocation toward the highest stored APR "
                        f"({inputs.highest_apr_pct:.2f}%). This does not change the debt balance."
                    )
                    if inputs.overpayment_basis == "apr" and inputs.highest_apr_pct is not None
                    else (
                        "No APR is stored on the active debts. This planning allocation goes to "
                        "the largest recorded balance and is not an interest ranking. "
                        "This does not change the debt balance."
                    )
                )
                items.append(
                    _make_item(
                        scope="personal",
                        kind="debt_overpayment",
                        category=label,
                        amount=over_amt,
                        source="generated",
                        source_record_type="liability",
                        source_record_id=inputs.highest_apr_debt_id,
                        notes=extra_notes,
                        record_href="/finance/debts",
                        slug=f"{inputs.highest_apr_debt_name}-extra",
                    )
                )
            else:
                items.append(
                    _make_item(
                        scope="personal",
                        kind="buffer",
                        category="Unallocated surplus held as cash",
                        amount=over_amt,
                        source="generated",
                        notes=(
                            "No debt with a known payment was available to receive an overpayment, "
                            "so this share stays as cash."
                        ),
                        slug="surplus-held-cash",
                    )
                )

        if disc_amt > ZERO:
            distributed = _distribute_discretionary(disc_amt, inputs.discretionary_categories)
            if distributed:
                for name, share in distributed:
                    items.append(
                        _make_item(
                            scope="personal",
                            kind="discretionary",
                            category=name,
                            amount=share,
                            source="transaction_average",
                            notes=(
                                "Share of available surplus, weighted by recorded average spend "
                                f"in {name}."
                            ),
                            slug=name,
                        )
                    )
            else:
                ref_note = ""
                if inputs.discretionary_reference_gbp is not None:
                    ref_note = (
                        f" Recorded monthly spending on file is "
                        f"£{inputs.discretionary_reference_gbp:,.2f}."
                    )
                items.append(
                    _make_item(
                        scope="personal",
                        kind="discretionary",
                        category="Discretionary spending",
                        amount=disc_amt,
                        source="generated",
                        notes=(
                            f"{base_strategy.replace('_', ' ').title()} share of available surplus."
                            + ref_note
                        ),
                        slug="discretionary",
                    )
                )

    totals_personal = calculate_budget_totals(items, "personal")
    totals_business = calculate_budget_totals(items, "business")
    totals_consolidated = calculate_budget_totals(items, "consolidated")

    recommended = False
    if strategy == "balanced" and totals_consolidated.income_complete:
        if totals_consolidated.surplus_gbp is not None and totals_consolidated.surplus_gbp >= 0:
            recommended = True

    return BudgetDraft(
        strategy=strategy,
        name=names[strategy],
        items=items,
        missing=missing,
        notes=notes,
        fingerprint=inputs.fingerprint,
        tax=inputs.tax,
        cash=inputs.cash,
        totals_personal=totals_personal,
        totals_business=totals_business,
        totals_consolidated=totals_consolidated,
        recommended=recommended,
    )


def generate_all_suggestions(inputs: BudgetInputs) -> list[BudgetDraft]:
    drafts = [
        generate_suggested_budget(inputs, "stabilise"),
        generate_suggested_budget(inputs, "balanced"),
        generate_suggested_budget(inputs, "debt_attack"),
        generate_suggested_budget(inputs, "custom"),
    ]
    if not any(d.recommended for d in drafts):
        drafts[0].recommended = True
    return drafts


def apply_overrides(
    items: list[BudgetDraftItem],
    overrides: dict[str, float | None],
) -> list[BudgetDraftItem]:
    """Apply user amounts by item key. Overrides survive source refreshes for the same key."""
    updated: list[BudgetDraftItem] = []
    for item in items:
        if item.key not in overrides:
            updated.append(item)
            continue
        raw = overrides[item.key]
        clone = BudgetDraftItem(**asdict(item))
        clone.is_user_override = True
        clone.source = "user_override"
        clone.source_label = _source_label("user_override")
        if raw is None:
            clone.amount_gbp = None
            clone.is_missing = True
        else:
            clone.amount_gbp = money(Decimal(str(raw)))
            clone.is_missing = False
        updated.append(clone)
    return updated


def merge_refresh_preserving_overrides(
    previous_items: list[BudgetDraftItem],
    regenerated_items: list[BudgetDraftItem],
) -> list[BudgetDraftItem]:
    """Keep user overrides when underlying records change; refresh generated figures."""
    previous_by_key = {item.key: item for item in previous_items}
    merged: list[BudgetDraftItem] = []
    seen: set[str] = set()
    for item in regenerated_items:
        seen.add(item.key)
        prior = previous_by_key.get(item.key)
        if prior and prior.is_user_override:
            clone = BudgetDraftItem(**asdict(item))
            clone.amount_gbp = prior.amount_gbp
            clone.is_missing = prior.amount_gbp is None
            clone.is_user_override = True
            clone.source = "user_override"
            clone.source_label = _source_label("user_override")
            clone.notes = prior.notes or clone.notes
            merged.append(clone)
        else:
            merged.append(item)
    for item in previous_items:
        if item.key in seen:
            continue
        if item.is_user_override or item.source in {"user_entered", "user_override"}:
            merged.append(item)
    return merged


def calculate_budget_variance(
    items: Iterable[BudgetDraftItem],
    transactions: Iterable[dict[str, Any]],
    *,
    month: str,
    view: BudgetView = "consolidated",
) -> BudgetVariance:
    """Compare planned amounts to recorded transactions. Does not invent actuals."""
    month_txs = [
        tx
        for tx in transactions
        if str(tx.get("transaction_date", "")).startswith(month)
    ]
    if not month_txs:
        return BudgetVariance(
            available=False,
            reason="No recorded transactions for this month. Budget vs actual is unavailable.",
            month=month,
            view=view,
            lines=[],
            unbudgeted_actuals=[],
            budgeted_total_gbp=0.0,
            actual_total_gbp=0.0,
        )

    selected = _visible_items(items, view)
    actual_by_category: dict[str, Decimal] = {}
    for tx in month_txs:
        tx_scope = tx.get("scope")
        if view != "consolidated" and tx_scope and tx_scope != view:
            continue
        category = (str(tx.get("category") or "").strip() or "Uncategorised").casefold()
        amount = Decimal(str(tx.get("amount_gbp") or 0))
        # Spending is negative; income is positive. Store signed actuals.
        actual_by_category[category] = actual_by_category.get(category, ZERO) + amount

    lines: list[VarianceLine] = []
    matched_categories: set[str] = set()
    budgeted_total = ZERO
    actual_total = ZERO
    for item in selected:
        cat_key = item.category.casefold()
        has_match = cat_key in actual_by_category
        actual_signed = actual_by_category.get(cat_key, ZERO)
        if has_match:
            matched_categories.add(cat_key)
        if item.kind == "income":
            actual_value = actual_signed if actual_signed > ZERO else ZERO
        else:
            actual_value = -actual_signed if actual_signed < ZERO else ZERO
        budgeted = (
            None
            if item.is_missing or item.amount_gbp is None
            else Decimal(str(item.amount_gbp))
        )
        # Totals compare planned allocations with recorded spend — not income + spend.
        if budgeted is not None and item.kind != "income":
            budgeted_total += budgeted
        if has_match and item.kind != "income":
            actual_total += actual_value
        variance = None
        if budgeted is not None and has_match:
            variance = budgeted - actual_value
        lines.append(
            VarianceLine(
                category=item.category,
                kind=item.kind,
                scope=item.scope,
                budgeted_gbp=None if budgeted is None else money(budgeted),
                actual_gbp=money(actual_value) if has_match else None,
                variance_gbp=None if variance is None else money(variance),
                is_missing=item.is_missing,
                matched=has_match,
            )
        )

    unbudgeted: list[VarianceLine] = []
    for category, signed in actual_by_category.items():
        if category in matched_categories:
            continue
        if signed == ZERO:
            continue
        kind = "income" if signed > ZERO else "other"
        actual_value = signed if signed > ZERO else -signed
        if kind != "income":
            actual_total += actual_value
        unbudgeted.append(
            VarianceLine(
                category=category,
                kind=kind,
                scope=view if view != "consolidated" else "personal",
                budgeted_gbp=None,
                actual_gbp=money(actual_value),
                variance_gbp=None,
                is_missing=True,
                matched=True,
            )
        )

    return BudgetVariance(
        available=True,
        reason="",
        month=month,
        view=view,
        lines=lines,
        unbudgeted_actuals=unbudgeted,
        budgeted_total_gbp=money(budgeted_total),
        actual_total_gbp=money(actual_total),
    )


def recommended_strategy(inputs: BudgetInputs) -> BudgetStrategy:
    """Balanced only when known figures support a non-negative surplus after mandatories."""
    unallocated = _unallocated_surplus(inputs)
    if unallocated is None or unallocated < ZERO:
        return "stabilise"
    return "balanced"
