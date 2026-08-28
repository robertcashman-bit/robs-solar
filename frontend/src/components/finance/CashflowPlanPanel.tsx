"use client";

import { formatGbp } from "@/lib/money";
import type { ScopedCashflowPlan } from "@/lib/finance-schemas";

type CashflowPlanPanelProps = {
  plan: ScopedCashflowPlan | null | undefined;
  loading?: boolean;
  title?: string;
};

export function CashflowPlanPanel({
  plan,
  loading = false,
  title,
}: CashflowPlanPanelProps) {
  if (loading) {
    return <p className="text-sm text-[var(--muted)]">Loading cashflow plan…</p>;
  }
  if (!plan) {
    return (
      <p className="rounded-xl border border-dashed border-[var(--border)] px-4 py-4 text-sm text-[var(--muted)]">
        Cashflow plan unavailable.
      </p>
    );
  }

  const label = title || `${plan.scope === "business" ? "Business" : "Personal"} cashflow plan`;

  return (
    <section aria-label={label} className="space-y-4">
      <div>
        <h3 className="solar-section-title text-base">{label}</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Starting bank {formatGbp(plan.starting_bank_gbp)} · overdraft limit{" "}
          {formatGbp(plan.overdraft_limit_gbp)} · headroom {formatGbp(plan.headroom_gbp)}
        </p>
      </div>

      {plan.live_breach ? (
        <p className="rounded-xl border border-rose-500/40 bg-rose-500/10 px-4 py-3 text-sm font-semibold">
          Live breach: current balance is already past the{" "}
          {formatGbp(plan.overdraft_limit_gbp)} overdraft facility.
        </p>
      ) : null}

      {plan.incomplete ? (
        <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
          Cashflow incomplete: {plan.incomplete_reason || "Income looks unreliable."}
        </p>
      ) : null}

      {plan.issues.length > 0 ? (
        <ul className="space-y-2">
          {plan.issues.map((issue) => (
            <li
              key={`${issue.kind}-${issue.message}`}
              className={`rounded-xl border px-4 py-3 text-sm ${
                issue.severity === "critical"
                  ? "border-rose-500/40 bg-rose-500/10"
                  : issue.severity === "warning"
                    ? "border-amber-500/40 bg-amber-500/10"
                    : "border-[var(--border)] bg-[var(--surface)]"
              }`}
            >
              {issue.message}
            </li>
          ))}
        </ul>
      ) : null}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] text-left text-sm">
          <thead>
            <tr className="border-b border-[var(--border)] text-[var(--muted)]">
              <th className="py-2 pr-3">Month</th>
              <th className="py-2 pr-3">Opening</th>
              <th className="py-2 pr-3">Income</th>
              <th className="py-2 pr-3">Spend</th>
              <th className="py-2 pr-3">Debt mins</th>
              <th className="py-2 pr-3">Closing</th>
              <th className="py-2">vs OD limit</th>
            </tr>
          </thead>
          <tbody>
            {plan.months.map((month) => (
              <tr key={month.month} className="border-b border-[var(--border)]">
                <td className="py-3 pr-3 font-medium">{month.label}</td>
                <td className="py-3 pr-3 tabular-nums">{formatGbp(month.opening_gbp)}</td>
                <td className="py-3 pr-3 tabular-nums">{formatGbp(month.income_gbp)}</td>
                <td className="py-3 pr-3 tabular-nums">{formatGbp(month.spending_gbp)}</td>
                <td className="py-3 pr-3 tabular-nums">{formatGbp(month.debt_payments_gbp)}</td>
                <td
                  className={`py-3 pr-3 tabular-nums font-semibold ${
                    month.breaches_overdraft ? "text-rose-700 dark:text-rose-300" : ""
                  }`}
                >
                  {formatGbp(month.closing_gbp)}
                </td>
                <td className="py-3 text-xs text-[var(--muted)]">
                  {month.breaches_overdraft
                    ? `Breach past -${formatGbp(month.overdraft_limit_gbp)}`
                    : `Headroom ${formatGbp(month.headroom_gbp)}`}
                  {month.notes.length > 0 ? ` · ${month.notes.join(" · ")}` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {plan.card_warnings.length > 0 ? (
        <div>
          <h4 className="text-sm font-semibold">Card limits</h4>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-[var(--muted)]">
            {plan.card_warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
