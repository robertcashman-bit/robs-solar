import type { FinanceDataGaps } from "@/lib/finance-schemas";

type FinanceDataGapsBannerProps = {
  gaps?: FinanceDataGaps | null;
  /** Extra lines computed locally (e.g. Debts page from liabilities). */
  extraLines?: string[];
};

function hasGaps(gaps?: FinanceDataGaps | null, extraLines?: string[]): boolean {
  if (extraLines && extraLines.length > 0) return true;
  if (!gaps) return false;
  return (
    gaps.unknown_apr_count > 0 ||
    gaps.missing_credit_limit_count > 0 ||
    gaps.monthly_interest_incomplete ||
    gaps.income_looks_thin
  );
}

export function FinanceDataGapsBanner({ gaps, extraLines = [] }: FinanceDataGapsBannerProps) {
  if (!hasGaps(gaps, extraLines)) return null;

  const lines: string[] = [...extraLines];
  if (gaps?.unknown_apr_count) {
    const names = gaps.unknown_apr_names.slice(0, 4).join(", ");
    lines.push(
      gaps.unknown_apr_count === 1
        ? `APR unknown: ${names || "1 debt"}.`
        : `APR unknown on ${gaps.unknown_apr_count} debts${names ? ` (${names}${gaps.unknown_apr_count > 4 ? "…" : ""})` : ""}.`,
    );
  }
  if (gaps?.missing_credit_limit_count) {
    const names = gaps.missing_credit_limit_names.slice(0, 4).join(", ");
    lines.push(
      gaps.missing_credit_limit_count === 1
        ? `Credit limit missing: ${names || "1 card"}.`
        : `Credit limits missing on ${gaps.missing_credit_limit_count} revolving debts${names ? ` (${names}${gaps.missing_credit_limit_count > 4 ? "…" : ""})` : ""}.`,
    );
  }
  if (gaps?.monthly_interest_incomplete) {
    lines.push("Monthly interest is incomplete until every repayable debt has an APR.");
  }
  if (gaps?.income_looks_thin) {
    lines.push(
      gaps.income_thin_note ||
        "Month income looks implausibly low — check the income source before trusting surplus.",
    );
  }

  return (
    <section
      aria-label="Data gaps"
      className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-100"
    >
      <p className="font-semibold">Data gaps — fill these in so the picture is complete</p>
      <ul className="mt-2 list-disc space-y-1 pl-5">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  );
}
