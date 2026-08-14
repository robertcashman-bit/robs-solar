import Link from "next/link";

import type { ActiveBudgetSummary, BudgetVariance, BudgetVarianceLine } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type BudgetVsActualPanelProps = {
  variance: BudgetVariance | null | undefined;
  activeBudget: ActiveBudgetSummary | null | undefined;
};

function amountCell(line: BudgetVarianceLine, field: "budgeted" | "actual" | "variance"): string {
  if (field === "budgeted") {
    return line.budgeted_gbp == null ? "Missing / needs input" : formatGbp(line.budgeted_gbp);
  }
  if (field === "actual") {
    if (!line.matched || line.actual_gbp == null) {
      return "No matching transactions";
    }
    return formatGbp(line.actual_gbp);
  }
  if (!line.matched || line.variance_gbp == null) {
    return "—";
  }
  return formatGbp(line.variance_gbp);
}

export function BudgetVsActualPanel({ variance, activeBudget }: BudgetVsActualPanelProps) {
  return (
    <section className="space-y-4" aria-label="Budget versus actual">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="solar-section-title">Budget vs actual</h2>
        <Link href="/finance/budget" className="solar-btn-ghost text-sm">
          Open Budget
        </Link>
      </div>
      {!activeBudget ? (
        <p className="rounded-xl border border-[var(--border)] px-4 py-3 text-sm text-[var(--muted)]">
          No active budget. Set one on the Budget page to compare planned amounts with recorded
          transactions.
        </p>
      ) : !variance || !variance.available ? (
        <p className="rounded-xl border border-[var(--border)] px-4 py-3 text-sm text-[var(--muted)]">
          {variance?.reason ||
            "Actual-versus-budget comparison is unavailable. No recorded transactions for this month."}
        </p>
      ) : (
        <div className="space-y-3">
          <p className="text-sm text-[var(--muted)]">
            Transactions are matched by category name. Totals compare planned allocations with
            recorded spend — income is listed but not added into the allocation total.
          </p>
          <div className="overflow-x-auto rounded-2xl border border-[var(--border)]">
            <table className="min-w-[640px] w-full text-sm">
              <caption className="sr-only">
                Budget versus actual for {activeBudget.name}
              </caption>
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Budgeted</th>
                  <th className="px-4 py-3">Actual</th>
                  <th className="px-4 py-3">Variance</th>
                </tr>
              </thead>
              <tbody>
                {variance.lines.map((line) => (
                  <tr key={`${line.scope}-${line.kind}-${line.category}`} className="border-b border-[var(--border)]">
                    <td className="px-4 py-3">{line.category}</td>
                    <td className="px-4 py-3 tabular-nums">{amountCell(line, "budgeted")}</td>
                    <td className="px-4 py-3 tabular-nums">{amountCell(line, "actual")}</td>
                    <td className="px-4 py-3 tabular-nums">{amountCell(line, "variance")}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-semibold">
                  <td className="px-4 py-3">Allocation total</td>
                  <td className="px-4 py-3 tabular-nums">{formatGbp(variance.budgeted_total_gbp)}</td>
                  <td className="px-4 py-3 tabular-nums">{formatGbp(variance.actual_total_gbp)}</td>
                  <td className="px-4 py-3 tabular-nums">
                    {formatGbp(variance.budgeted_total_gbp - variance.actual_total_gbp)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          {variance.unbudgeted_actuals.length > 0 ? (
            <div className="overflow-x-auto rounded-2xl border border-[var(--border)]">
              <table className="min-w-[640px] w-full text-sm">
                <caption className="px-4 py-3 text-left text-sm font-medium">
                  Recorded transactions that do not match a budget category
                </caption>
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Actual</th>
                  </tr>
                </thead>
                <tbody>
                  {variance.unbudgeted_actuals.map((line) => (
                    <tr key={`unbudgeted-${line.scope}-${line.category}`} className="border-b border-[var(--border)]">
                      <td className="px-4 py-3">{line.category}</td>
                      <td className="px-4 py-3 tabular-nums">
                        {line.actual_gbp == null ? "—" : formatGbp(line.actual_gbp)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
