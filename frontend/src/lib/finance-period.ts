export const FINANCE_PERIOD_KEYS = ["mtd", "1m", "3m", "6m", "12m", "24m"] as const;
export type FinancePeriodKey = (typeof FINANCE_PERIOD_KEYS)[number];

export const FINANCE_PERIOD_SCOPES = ["personal", "business", "both"] as const;
export type FinancePeriodScope = (typeof FINANCE_PERIOD_SCOPES)[number];

export const FINANCE_PERIOD_LABELS: Record<FinancePeriodKey, string> = {
  mtd: "This month to date",
  "1m": "Last month",
  "3m": "3 months",
  "6m": "6 months",
  "12m": "Last year",
  "24m": "2 years",
};

/** Calendar-month lookbacks ending last month (exclude in-progress month). */
const CALENDAR_LOOKBACK_MONTHS: Partial<Record<FinancePeriodKey, number>> = {
  "1m": 1,
  "3m": 3,
  "6m": 6,
};

/** Rolling lookbacks through today (include current month). */
const ROLLING_LOOKBACK_MONTHS: Partial<Record<FinancePeriodKey, number>> = {
  "12m": 12,
  "24m": 24,
};

export const DEFAULT_FINANCE_PERIOD: FinancePeriodKey = "1m";
export const DEFAULT_FINANCE_SCOPE: FinancePeriodScope = "personal";

/** Overview default: last complete month on day 1 so DLS does not look empty. */
export function overviewDefaultPeriod(asOf: Date = new Date()): FinancePeriodKey {
  // Prefer UK/local calendar day for "first of the month" readability.
  const day = asOf.getDate();
  return day <= 1 ? "1m" : "mtd";
}

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

function utcYmd(year: number, monthIndex: number, day: number): string {
  return new Date(Date.UTC(year, monthIndex, day)).toISOString().slice(0, 10);
}

function subtractMonthsUtc(asOf: Date, months: number): { year: number; monthIndex: number; day: number } {
  const year = asOf.getUTCFullYear();
  const monthIndex = asOf.getUTCMonth();
  const day = asOf.getUTCDate();
  const target = new Date(Date.UTC(year, monthIndex - months, 1));
  const lastDay = new Date(
    Date.UTC(target.getUTCFullYear(), target.getUTCMonth() + 1, 0),
  ).getUTCDate();
  return {
    year: target.getUTCFullYear(),
    monthIndex: target.getUTCMonth(),
    day: Math.min(day, lastDay),
  };
}

/** Inclusive ISO date window. mtd → today; 1m/3m/6m end last month; 12m/24m roll through today. */
export function periodDateRange(
  period: FinancePeriodKey,
  asOf: Date = new Date(),
): { dateFrom: string; dateTo: string; monthsRequested: number } {
  if (period === "mtd") {
    const dateFrom = utcYmd(asOf.getUTCFullYear(), asOf.getUTCMonth(), 1);
    const dateTo = utcYmd(asOf.getUTCFullYear(), asOf.getUTCMonth(), asOf.getUTCDate());
    return { dateFrom, dateTo, monthsRequested: 1 };
  }

  const rollingMonths = ROLLING_LOOKBACK_MONTHS[period];
  if (rollingMonths != null) {
    const start = subtractMonthsUtc(asOf, rollingMonths);
    const dateFrom = utcYmd(start.year, start.monthIndex, start.day);
    const dateTo = utcYmd(asOf.getUTCFullYear(), asOf.getUTCMonth(), asOf.getUTCDate());
    return { dateFrom, dateTo, monthsRequested: rollingMonths };
  }

  const monthsRequested = CALENDAR_LOOKBACK_MONTHS[period] ?? 1;
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
