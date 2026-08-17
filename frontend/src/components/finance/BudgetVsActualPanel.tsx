"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { ActiveBudgetSummary, BudgetVsActual } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type BudgetVsActualPanelProps = {
  variance: BudgetVsActual | null | undefined;
  activeBudget: ActiveBudgetSummary | null | undefined;
};

function amountCell(
  line: BudgetVsActual["lines"][number],
  field: "budget" | "actual" | "variance",
): string {
  if (field === "budget") {
    return formatGbp(line.budget_gbp);
  }
  if (field === "actual") {
    if (line.missing_actual || line.actual_gbp == null) {
      return "Missing";
    }
    return formatGbp(line.actual_gbp);
  }
  if (line.missing_actual || line.variance_gbp == null) {
    return "—";
  }
  return formatGbp(line.variance_gbp);
}

export function BudgetVsActualPanel({ variance, activeBudget }: BudgetVsActualPanelProps) {
  const [hideRecorded, setHideRecorded] = useState(false);
  const visibleLines = useMemo(() => {
    const lines = variance?.lines ?? [];
    if (!hideRecorded) return lines;
    return lines.filter((line) => line.missing_actual);
  }, [hideRecorded, variance?.lines]);

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
          actuals.
        </p>
      ) : !variance || !variance.available ? (
        <p className="rounded-xl border border-[var(--border)] px-4 py-3 text-sm text-[var(--muted)]">
          {variance?.reason ||
            "Actual-versus-budget comparison is unavailable for this month."}
        </p>
      ) : (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-[var(--muted)]">
              Compare {activeBudget.name} with recorded actuals
              {variance.plan_name ? ` for ${variance.month}` : ""}. Blank actuals stay missing —
              they are not treated as £0. Enter figures on the Budget page.
            </p>
            <label className="flex items-center gap-2 text-sm text-[var(--muted)]">
              <input
                type="checkbox"
                checked={hideRecorded}
                onChange={(event) => setHideRecorded(event.target.checked)}
              />
              Hide recorded
            </label>
          </div>
          <div className="overflow-x-auto rounded-2xl border border-[var(--border)]">
            <table className="min-w-[640px] w-full text-sm">
              <caption className="sr-only">
                Budget versus actual for {activeBudget.name}
              </caption>
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Budget</th>
                  <th className="px-4 py-3">Actual</th>
                  <th className="px-4 py-3">Forecast</th>
                  <th className="px-4 py-3">Remaining</th>
                </tr>
              </thead>
              <tbody>
                {visibleLines.map((line) => (
                  <tr key={`${line.scope}-${line.category}`} className="border-b border-[var(--border)]">
                    <td className="px-4 py-3">
                      {line.category}
                      <span className="ml-2 text-xs text-[var(--muted)]">{line.scope}</span>
                    </td>
                    <td className="px-4 py-3 tabular-nums">{amountCell(line, "budget")}</td>
                    <td className="px-4 py-3 tabular-nums">{amountCell(line, "actual")}</td>
                    <td className="px-4 py-3 tabular-nums">
                      {line.forecast_gbp == null ? "—" : formatGbp(line.forecast_gbp)}
                    </td>
                    <td className="px-4 py-3 tabular-nums">{amountCell(line, "variance")}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr className="font-semibold">
                  <td className="px-4 py-3">Allocation total</td>
                  <td className="px-4 py-3 tabular-nums">{formatGbp(variance.budgeted_total_gbp)}</td>
                  <td className="px-4 py-3 tabular-nums">{formatGbp(variance.actual_total_gbp)}</td>
                  <td className="px-4 py-3 tabular-nums">—</td>
                  <td className="px-4 py-3 tabular-nums">
                    {variance.variance_total_gbp == null
                      ? "—"
                      : formatGbp(variance.variance_total_gbp)}
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
          {variance.unbudgeted_actuals.length > 0 ? (
            <div className="overflow-x-auto rounded-2xl border border-[var(--border)]">
              <table className="min-w-[640px] w-full text-sm">
                <caption className="px-4 py-3 text-left text-sm font-medium">
                  Recorded actuals that do not match a budget category
                </caption>
                <thead>
                  <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                    <th className="px-4 py-3">Category</th>
                    <th className="px-4 py-3">Actual</th>
                  </tr>
                </thead>
                <tbody>
                  {variance.unbudgeted_actuals.map((line) => (
                    <tr
                      key={`unbudgeted-${line.scope}-${line.category}`}
                      className="border-b border-[var(--border)]"
                    >
                      <td className="px-4 py-3">
                        {line.category}
                        <span className="ml-2 text-xs text-[var(--muted)]">{line.scope}</span>
                      </td>
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
