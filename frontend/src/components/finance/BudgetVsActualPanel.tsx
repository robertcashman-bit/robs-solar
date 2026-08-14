import Link from "next/link";

import type { ActiveBudgetSummary, BudgetVariance } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type BudgetVsActualPanelProps = {
  variance: BudgetVariance | null | undefined;
  activeBudget: ActiveBudgetSummary | null | undefined;
};

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
                  <td className="px-4 py-3 tabular-nums">
                    {line.budgeted_gbp == null ? "Missing / needs input" : formatGbp(line.budgeted_gbp)}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{formatGbp(line.actual_gbp)}</td>
                  <td className="px-4 py-3 tabular-nums">
                    {line.variance_gbp == null ? "—" : formatGbp(line.variance_gbp)}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="font-semibold">
                <td className="px-4 py-3">Total</td>
                <td className="px-4 py-3 tabular-nums">{formatGbp(variance.budgeted_total_gbp)}</td>
                <td className="px-4 py-3 tabular-nums">{formatGbp(variance.actual_total_gbp)}</td>
                <td className="px-4 py-3 tabular-nums">
                  {formatGbp(variance.budgeted_total_gbp - variance.actual_total_gbp)}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}
    </section>
  );
}
