export function formatGbp(value: number | null | undefined, decimals = 2): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency: "GBP",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatPercent(value: number | null | undefined, decimals = 1): string {
  if (value == null || Number.isNaN(value)) {
    return "—";
  }
  return `${value.toFixed(decimals)}%`;
}

export function formatMonthLabel(month: string): string {
  const [year, mon] = month.split("-");
  const date = new Date(Number(year), Number(mon) - 1, 1);
  return date.toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

/** Parse a required amount. Empty or non-numeric input is invalid — never coerced to 0. */
export function parseRequiredAmount(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) {
    return null;
  }
  const value = Number(trimmed);
  return Number.isFinite(value) ? value : null;
}

/** Parse an optional amount. Empty means omitted; invalid is null. */
export function parseOptionalAmount(raw: string): number | null | undefined {
  const trimmed = raw.trim();
  if (!trimmed) {
    return undefined;
  }
  return parseRequiredAmount(trimmed);
}

export function parseMoneyInput(raw: string): number | null {
  const value = parseGbp(raw);
  return Number.isNaN(value) ? null : value;
}

export function parseGbp(value: string): number {
  const cleaned = value.replace(/[£,\s]/g, "").trim();
  if (!cleaned) return Number.NaN;
  return Number(cleaned);
}

export function currentMonthKey(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

/** True when a stored snapshot date (`YYYY-MM` or `YYYY-MM-DD`) is in `month`. */
export function isCurrentMonthSnapshot(snapshotDate: string, month = currentMonthKey()): boolean {
  return snapshotDate === month || snapshotDate.startsWith(month);
}
