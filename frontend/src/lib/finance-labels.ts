/** Human-readable labels for internal finance codes shown in the UI. */

const RECON_KIND_LABELS: Record<string, string> = {
  opening_balance_unknown: "Opening balance unknown",
  opening_balance_mismatch: "Opening balance mismatch",
  ledger_mismatch: "Ledger mismatch",
  balance_mismatch: "Balance mismatch",
};

const RECON_STATUS_LABELS: Record<string, string> = {
  insufficient_data: "insufficient history",
  unresolved: "unresolved",
  confirmed: "confirmed",
  ignored: "ignored",
};

const DATA_QUALITY_ISSUE_LABELS: Record<string, string> = {
  possible_personal_on_business: "Looks personal on a business account",
  possible_business_on_personal: "Looks business on a personal account",
  missing_category: "Missing category",
  missing_date: "Missing date",
  duplicate_suspect: "Possible duplicate",
};

export function formatReconFlagLabel(kind: string, status: string): string {
  const kindLabel = RECON_KIND_LABELS[kind] ?? kind.replaceAll("_", " ");
  const statusLabel = RECON_STATUS_LABELS[status] ?? status.replaceAll("_", " ");
  return `${kindLabel} (${statusLabel})`;
}

export function formatDataQualityIssue(issue: string): string {
  return DATA_QUALITY_ISSUE_LABELS[issue] ?? issue.replaceAll("_", " ");
}

/** Format an ISO / Date for UK display, matching QuickFile sync stamps. */
export function formatUkDateTime(value: string | Date | null | undefined): string {
  if (value == null || value === "") return "";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-GB");
}
