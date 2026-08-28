"use client";

import { formatGbp, formatPercent } from "@/lib/money";
import type { DebtStrategy } from "@/lib/finance-schemas";

type DebtReductionPlanPanelProps = {
  plan: DebtStrategy | null | undefined;
  loading?: boolean;
  title?: string;
};

export function DebtReductionPlanPanel({
  plan,
  loading = false,
  title,
}: DebtReductionPlanPanelProps) {
  if (loading) {
    return <p className="text-sm text-[var(--muted)]">Loading debt reduction plan…</p>;
  }
  if (!plan) {
    return (
      <p className="rounded-xl border border-dashed border-[var(--border)] px-4 py-4 text-sm text-[var(--muted)]">
        Debt reduction plan unavailable.
      </p>
    );
  }

  const heading = title || plan.headline;
  const rows = plan.debts.length > 0 ? plan.debts : plan.payoff_order;

  return (
    <section aria-label={heading} className="space-y-4">
      <div>
        <h3 className="solar-section-title text-base">{heading}</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">{plan.message}</p>
      </div>
      {plan.incomplete ? (
        <p className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm">
          Plan incomplete: {plan.incomplete_reason || "One or more APRs are unknown."}
        </p>
      ) : null}
      {plan.focus_debt_name ? (
        <p className="text-sm">
          Recommended focus: <span className="font-semibold">{plan.focus_debt_name}</span>
          {plan.estimated_debt_free_date
            ? ` · focus payoff target ${plan.estimated_debt_free_date}`
            : ""}
        </p>
      ) : null}

      {rows.length > 0 ? (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead>
              <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                <th className="py-2 pr-3">Payoff order</th>
                <th className="py-2 pr-3">Balance</th>
                <th className="py-2 pr-3">APR</th>
                <th className="py-2 pr-3">Min payment</th>
                <th className="py-2 pr-3">Interest / mo</th>
                <th className="py-2">Why</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((raw, index) => {
                const row = raw as Record<string, unknown>;
                const name = String(row.name ?? "");
                const balance = Number(row.balance_gbp ?? 0);
                const aprKnown = row.interest_rate_known !== false && row.apr_known !== false;
                const apr = Number(row.interest_rate_pct ?? 0);
                const minPay = Number(row.minimum_payment_gbp ?? 0);
                const interest =
                  row.monthly_interest_gbp == null
                    ? null
                    : Number(row.monthly_interest_gbp);
                const reason =
                  typeof row.order_reason === "string"
                    ? row.order_reason
                    : String(row.priority_label ?? "");
                const isMortgage = Boolean(row.is_mortgage) || row.debt_type === "mortgage";
                const isFocus = Boolean(row.is_focus);
                return (
                  <tr key={String(row.id ?? name)} className="border-b border-[var(--border)] align-top">
                    <td className="py-3 pr-3">
                      <span className="font-medium">
                        {index + 1}. {name}
                      </span>
                      {isFocus ? (
                        <span className="ml-2 text-xs font-semibold uppercase text-emerald-700 dark:text-emerald-400">
                          Focus
                        </span>
                      ) : null}
                      {isMortgage ? (
                        <span className="mt-1 block text-xs text-[var(--muted)]">
                          House mortgage · confirmed half of £164,421 joint
                        </span>
                      ) : null}
                    </td>
                    <td className="py-3 pr-3 tabular-nums">{formatGbp(balance)}</td>
                    <td className="py-3 pr-3">
                      {aprKnown === false || !(Number(row.interest_rate_pct) > 0)
                        ? "APR unknown"
                        : formatPercent(apr)}
                    </td>
                    <td className="py-3 pr-3 tabular-nums">{formatGbp(minPay)}</td>
                    <td className="py-3 pr-3 tabular-nums">
                      {interest == null ? "Incomplete" : formatGbp(interest)}
                    </td>
                    <td className="py-3 text-xs text-[var(--muted)]">{reason}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-[var(--muted)]">No repayable debts in this stack.</p>
      )}

      {plan.milestones.length > 0 ? (
        <div>
          <h4 className="text-sm font-semibold">Payoff milestones (minimum payments)</h4>
          <ul className="mt-2 space-y-2 text-sm">
            {plan.milestones.map((item) => (
              <li
                key={`${item.month_index}-${item.focus_debt_name ?? "remain"}`}
                className="rounded-xl border border-[var(--border)] px-3 py-2"
              >
                <span className="font-medium">{item.label}</span>
                {item.focus_debt_name ? ` · ${item.focus_debt_name}` : ""}
                <span className="block text-xs text-[var(--muted)]">
                  Remaining {formatGbp(item.remaining_total_gbp)}
                  {item.note ? ` — ${item.note}` : ""}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {plan.scenarios.length > 0 ? (
        <div>
          <h4 className="text-sm font-semibold">What if I paid extra on this stack?</h4>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full min-w-[520px] text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--border)] text-[var(--muted)]">
                  <th className="py-2 pr-3">Extra / month</th>
                  <th className="py-2 pr-3">Months saved</th>
                  <th className="py-2 pr-3">Interest saved</th>
                  <th className="py-2">Note</th>
                </tr>
              </thead>
              <tbody>
                {plan.scenarios.map((row) => (
                  <tr key={row.extra_gbp} className="border-b border-[var(--border)]">
                    <td className="py-2 pr-3 tabular-nums">{formatGbp(row.extra_gbp)}</td>
                    <td className="py-2 pr-3">
                      {row.incomplete
                        ? "—"
                        : row.months_saved == null
                          ? "—"
                          : `${row.months_saved} mo`}
                    </td>
                    <td className="py-2 pr-3 tabular-nums">
                      {row.interest_saved_gbp == null ? "—" : formatGbp(row.interest_saved_gbp)}
                    </td>
                    <td className="py-2 text-xs text-[var(--muted)]">{row.reason || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}
