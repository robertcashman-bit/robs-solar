/**
 * Canonical client-side budget totals.
 * Must stay aligned with backend/app/services/finance/budget_engine.py
 * calculate_budget_totals / to_monthly_amount / parse_budget_amount.
 */

export type BudgetView = "personal" | "business" | "consolidated";

export type BudgetItemLike = {
  key: string;
  scope: "personal" | "business";
  kind: string;
  amount_gbp: number | null;
  is_missing: boolean;
  is_transfer: boolean;
};

export type BudgetTotals = {
  view: BudgetView;
  income_gbp: number;
  essential_gbp: number;
  debt_minimum_gbp: number;
  debt_overpayment_gbp: number;
  tax_provision_gbp: number;
  buffer_gbp: number;
  discretionary_gbp: number;
  other_gbp: number;
  committed_gbp: number;
  allocated_gbp: number;
  surplus_gbp: number | null;
  income_complete: boolean;
  has_missing_inputs: boolean;
  is_deficit: boolean;
  incomplete_reason: string;
};

const FREQUENCY_TO_MONTHLY: Record<string, number> = {
  weekly: 52 / 12,
  fortnightly: 26 / 12,
  four_weekly: 13 / 12,
  monthly: 1,
  annual: 1 / 12,
};

const MANDATORY_KINDS = new Set(["essential", "debt_minimum", "tax_provision"]);

export function money(value: number): number {
  return Math.round((value + Number.EPSILON) * 100) / 100;
}

export function toMonthlyAmount(amount: number, frequency: string): number {
  const factor = FREQUENCY_TO_MONTHLY[frequency];
  if (factor == null) {
    throw new Error(`Unsupported payment frequency: ${frequency}`);
  }
  return money(amount * factor);
}

/** Blank is missing (null), not zero. Pasted currency is accepted. */
export function parseBudgetAmount(raw: string): number | null {
  const trimmed = raw.trim().replace(/[£$,]/g, "");
  if (!trimmed) {
    return null;
  }
  const amount = Number(trimmed);
  if (!Number.isFinite(amount)) {
    throw new Error("Amount must be a number. Blank values are not saved as zero.");
  }
  return amount;
}

function visibleItems(items: BudgetItemLike[], view: BudgetView): BudgetItemLike[] {
  if (view === "consolidated") {
    return items.filter((item) => !item.is_transfer);
  }
  return items.filter((item) => item.scope === view);
}

function sumKind(items: BudgetItemLike[], kind: string): number {
  return items.reduce((sum, item) => {
    if (item.kind !== kind || item.is_missing || item.amount_gbp == null) {
      return sum;
    }
    return sum + item.amount_gbp;
  }, 0);
}

export function calculateBudgetTotals(
  items: BudgetItemLike[],
  view: BudgetView = "consolidated",
): BudgetTotals {
  const selected = visibleItems(items, view);
  const incomeItems = selected.filter((item) => item.kind === "income");
  const incomeComplete =
    incomeItems.length > 0 &&
    incomeItems.every((item) => !item.is_missing && item.amount_gbp != null);

  const income = sumKind(selected, "income");
  const essential = sumKind(selected, "essential");
  const debtMinimum = sumKind(selected, "debt_minimum");
  const debtOverpayment = sumKind(selected, "debt_overpayment");
  const tax = sumKind(selected, "tax_provision");
  const buffer = sumKind(selected, "buffer");
  const discretionary = sumKind(selected, "discretionary");
  const other = sumKind(selected, "other");
  const committed = essential + debtMinimum + tax;
  const allocated = essential + debtMinimum + debtOverpayment + tax + buffer + discretionary + other;

  let surplus: number | null = null;
  let incompleteReason = "";
  if (!incomeComplete) {
    incompleteReason = "Projected surplus unavailable — monthly income needs input.";
  } else {
    surplus = money(income - allocated);
  }

  const hasMissingInputs = selected.some(
    (item) => item.is_missing && (MANDATORY_KINDS.has(item.kind) || item.kind === "income"),
  );

  return {
    view,
    income_gbp: money(income),
    essential_gbp: money(essential),
    debt_minimum_gbp: money(debtMinimum),
    debt_overpayment_gbp: money(debtOverpayment),
    tax_provision_gbp: money(tax),
    buffer_gbp: money(buffer),
    discretionary_gbp: money(discretionary),
    other_gbp: money(other),
    committed_gbp: money(committed),
    allocated_gbp: money(allocated),
    surplus_gbp: surplus,
    income_complete: incomeComplete,
    has_missing_inputs: hasMissingInputs,
    is_deficit: surplus != null && surplus < 0,
    incomplete_reason: incompleteReason,
  };
}

export function calculateMandatoryCommitments(
  items: BudgetItemLike[],
  view: BudgetView = "consolidated",
): number {
  return money(
    visibleItems(items, view).reduce((sum, item) => {
      if (!MANDATORY_KINDS.has(item.kind) || item.is_missing || item.amount_gbp == null) {
        return sum;
      }
      return sum + item.amount_gbp;
    }, 0),
  );
}
