import Link from "next/link";

import type { ActiveBudgetSummary } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type ActiveBudgetCardProps = {
  budget: ActiveBudgetSummary | null | undefined;
};

export function ActiveBudgetCard({ budget }: ActiveBudgetCardProps) {
  if (!budget) {
    return (
      <section
        aria-label="Active budget"
        className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5"
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Active Budget</h2>
            <p className="mt-0.5 text-sm text-[var(--muted)]">No budget is active yet.</p>
          </div>
          <Link href="/finance/budget" className="solar-btn-secondary text-sm">
            Open Budget
          </Link>
        </div>
      </section>
    );
  }

  const surplus = budget.surplus_gbp;
  const surplusLabel =
    surplus < 0
      ? `Projected monthly shortfall: ${formatGbp(Math.abs(surplus))}`
      : `Projected monthly surplus: ${formatGbp(surplus)}`;
  const surplusClass =
    surplus < 0 ? "text-red-600 dark:text-red-400" : "text-emerald-600 dark:text-emerald-400";

  return (
    <section
      aria-label="Active budget"
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-lg font-semibold">Active Budget</h2>
            <span className="rounded-full bg-emerald-600 px-2 py-0.5 text-xs font-semibold text-white">
              Active
            </span>
          </div>
          <p className="mt-0.5 text-sm text-[var(--muted)]">
            {budget.name} · {budget.style.replaceAll("_", " ")}. A plan, not actual cashflow.
          </p>
        </div>
        <Link href="/finance/budget" className="solar-btn-secondary text-sm">
          Open Budget
        </Link>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-3 py-2">
          <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">Monthly income</dt>
          <dd className="mt-1 text-lg font-semibold tabular-nums">{formatGbp(budget.income_gbp)}</dd>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-3 py-2">
          <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">Planned expenditure</dt>
          <dd className="mt-1 text-lg font-semibold tabular-nums">
            {formatGbp(budget.monthly_total_gbp)}
          </dd>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-3 py-2">
          <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">Debt overpayment</dt>
          <dd className="mt-1 text-lg font-semibold tabular-nums">
            {formatGbp(budget.debt_overpayment_gbp)}
          </dd>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)]/40 px-3 py-2">
          <dt className="text-xs uppercase tracking-wide text-[var(--muted)]">Surplus / deficit</dt>
          <dd className={`mt-1 text-sm font-semibold ${surplusClass}`}>{surplusLabel}</dd>
        </div>
      </dl>
    </section>
  );
}
