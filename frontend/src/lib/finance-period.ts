export const FINANCE_PERIOD_KEYS = ["mtd", "1m", "3m", "6m", "12m"] as const;
export type FinancePeriodKey = (typeof FINANCE_PERIOD_KEYS)[number];

export const FINANCE_PERIOD_SCOPES = ["personal", "business", "both"] as const;
export type FinancePeriodScope = (typeof FINANCE_PERIOD_SCOPES)[number];

export const FINANCE_PERIOD_LABELS: Record<FinancePeriodKey, string> = {
  mtd: "This month to date",
  "1m": "Last month",
  "3m": "3 months",
  "6m": "6 months",
  "12m": "Last year",
};

export const DEFAULT_FINANCE_PERIOD: FinancePeriodKey = "1m";
export const DEFAULT_FINANCE_SCOPE: FinancePeriodScope = "personal";

export const FINANCE_PERIOD_STORAGE_KEY = "finance.period.v1";

export type FinancePeriodPrefs = {
  period: FinancePeriodKey;
  personalPeriod: FinancePeriodKey;
  businessPeriod: FinancePeriodKey;
  scope: FinancePeriodScope;
};

export function isFinancePeriodKey(value: string | null | undefined): value is FinancePeriodKey {
  return FINANCE_PERIOD_KEYS.includes(value as FinancePeriodKey);
}

export function isFinancePeriodScope(value: string | null | undefined): value is FinancePeriodScope {
  return FINANCE_PERIOD_SCOPES.includes(value as FinancePeriodScope);
}

export function parseFinancePeriod(
  value: string | null | undefined,
  fallback: FinancePeriodKey = DEFAULT_FINANCE_PERIOD,
): FinancePeriodKey {
  return isFinancePeriodKey(value) ? value : fallback;
}

export function parseFinanceScope(
  value: string | null | undefined,
  fallback: FinancePeriodScope = DEFAULT_FINANCE_SCOPE,
): FinancePeriodScope {
  return isFinancePeriodScope(value) ? value : fallback;
}

export function periodLabel(period: FinancePeriodKey): string {
  return FINANCE_PERIOD_LABELS[period];
}

/** Inclusive ISO date window. Historical keys end last month; mtd is month start→today. */
export function periodDateRange(
  period: FinancePeriodKey,
  asOf: Date = new Date(),
): { dateFrom: string; dateTo: string; monthsRequested: number } {
  if (period === "mtd") {
    const dateFrom = new Date(Date.UTC(asOf.getUTCFullYear(), asOf.getUTCMonth(), 1))
      .toISOString()
      .slice(0, 10);
    const dateTo = new Date(Date.UTC(asOf.getUTCFullYear(), asOf.getUTCMonth(), asOf.getUTCDate()))
      .toISOString()
      .slice(0, 10);
    return { dateFrom, dateTo, monthsRequested: 1 };
  }
  const monthsRequested = { "1m": 1, "3m": 3, "6m": 6, "12m": 12 }[period];
  const end = new Date(Date.UTC(asOf.getUTCFullYear(), asOf.getUTCMonth() - 1, 1));
  const start = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth() - (monthsRequested - 1), 1));
  const dateFrom = start.toISOString().slice(0, 10);
  const lastDay = new Date(Date.UTC(end.getUTCFullYear(), end.getUTCMonth() + 1, 0));
  const dateTo = lastDay.toISOString().slice(0, 10);
  return { dateFrom, dateTo, monthsRequested };
}

export function readStoredPeriodPrefs(): Partial<FinancePeriodPrefs> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(FINANCE_PERIOD_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Partial<FinancePeriodPrefs>;
    return {
      period: parseFinancePeriod(parsed.period),
      personalPeriod: parseFinancePeriod(parsed.personalPeriod ?? parsed.period),
      businessPeriod: parseFinancePeriod(parsed.businessPeriod ?? parsed.period),
      scope: parseFinanceScope(parsed.scope),
    };
  } catch {
    return {};
  }
}

export function writeStoredPeriodPrefs(prefs: FinancePeriodPrefs): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(FINANCE_PERIOD_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // ignore private mode / quota
  }
}
