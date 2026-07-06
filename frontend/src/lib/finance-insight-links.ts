import type { FinanceInsight } from "@/lib/finance-schemas";

const CATEGORY_LABELS: Record<FinanceInsight["category"], string> = {
  cashflow: "Cash flow",
  debt: "Debts",
  tax: "Tax & reserves",
  business: "Business",
  energy: "Energy",
};

const CATEGORY_HREFS: Record<FinanceInsight["category"], string> = {
  cashflow: "/finance/cash-flow",
  debt: "/finance/debts",
  tax: "/finance/business",
  business: "/finance/business",
  energy: "/energy",
};

export function insightCategoryLabel(category: FinanceInsight["category"]): string {
  return CATEGORY_LABELS[category] ?? category;
}

export function insightCategoryHref(category: FinanceInsight["category"]): string {
  return CATEGORY_HREFS[category] ?? "/";
}

const SEVERITY_ORDER: Record<FinanceInsight["severity"], number> = {
  critical: 0,
  warning: 1,
  info: 2,
};

export function sortInsights(insights: FinanceInsight[]): FinanceInsight[] {
  return [...insights].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity],
  );
}
