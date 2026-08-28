import { debtUsesCreditLimit } from "@/lib/finance-form";
import type { FinanceLiability } from "@/lib/finance-schemas";

export const MORTGAGE_HINT = "Confirmed half-share of £164,421 joint mortgage.";
export const STALE_MORTGAGE_ORIGINAL_GBP = 175000;

export type DebtGroupKey =
  | "personal_credit_cards"
  | "personal_loans"
  | "house_mortgage"
  | "personal_other"
  | "business_credit_cards"
  | "business_loans"
  | "business_other";

export type DebtGroup = {
  key: DebtGroupKey;
  title: string;
  scope: "personal" | "business";
  debts: FinanceLiability[];
};

const GROUP_ORDER: DebtGroupKey[] = [
  "personal_credit_cards",
  "personal_loans",
  "house_mortgage",
  "personal_other",
  "business_credit_cards",
  "business_loans",
  "business_other",
];

const GROUP_TITLES: Record<DebtGroupKey, string> = {
  personal_credit_cards: "Personal credit cards",
  personal_loans: "Personal loans",
  house_mortgage: "House mortgage",
  personal_other: "Personal other",
  business_credit_cards: "Business credit cards",
  business_loans: "Business loans",
  business_other: "Business other",
};

export function debtGroupKey(debt: FinanceLiability): DebtGroupKey {
  if (debt.scope === "personal") {
    if (debt.debt_type === "credit_card") return "personal_credit_cards";
    if (debt.debt_type === "loan") return "personal_loans";
    if (debt.debt_type === "mortgage") return "house_mortgage";
    return "personal_other";
  }
  if (debt.debt_type === "credit_card") return "business_credit_cards";
  if (debt.debt_type === "loan" || debt.debt_type === "business_loan") {
    return "business_loans";
  }
  return "business_other";
}

export function groupDebts(debts: FinanceLiability[]): DebtGroup[] {
  const buckets = new Map<DebtGroupKey, FinanceLiability[]>();
  for (const key of GROUP_ORDER) buckets.set(key, []);
  for (const debt of debts) {
    const key = debtGroupKey(debt);
    buckets.get(key)!.push(debt);
  }
  return GROUP_ORDER.filter((key) => (buckets.get(key)?.length ?? 0) > 0).map((key) => ({
    key,
    title: GROUP_TITLES[key],
    scope: key.startsWith("business") ? "business" : "personal",
    debts: buckets.get(key)!,
  }));
}

/** Hide the stale £175k mortgage placeholder in edit forms / displays. */
export function displayOriginalBalanceGbp(debt: FinanceLiability): number | null {
  const original = debt.original_balance_gbp;
  if (original == null) return null;
  if (
    debt.debt_type === "mortgage" &&
    Math.abs(original - STALE_MORTGAGE_ORIGINAL_GBP) < 0.01
  ) {
    return 82210.5;
  }
  return original;
}

export function debtGapLabels(debt: FinanceLiability): string[] {
  const gaps: string[] = [];
  if (debt.interest_rate_known === false) gaps.push("APR unknown");
  if (
    debtUsesCreditLimit(debt.debt_type) &&
    (debt.credit_limit_gbp == null || debt.credit_limit_gbp <= 0)
  ) {
    gaps.push("Credit limit missing");
  }
  return gaps;
}

export function round2(value: number): number {
  return Math.round(value * 100) / 100;
}
