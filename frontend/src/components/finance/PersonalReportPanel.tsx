"use client";

import Link from "next/link";

import { MetricTile } from "@/components/finance/MetricTile";
import type { PersonalFinanceReport } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

type PersonalReportPanelProps = {
  report: PersonalFinanceReport | null | undefined;
};

function changeHint(change: number | null | undefined, previous: number | null | undefined): string | undefined {
  if (change == null || previous == null) {
    return undefined;
  }
  const sign = change > 0 ? "+" : "";
  return `${sign}${formatGbp(change)} vs previous month`;
}

export function PersonalReportPanel({ report }: PersonalReportPanelProps) {
  if (!report) {
    return (
      <section aria-label="Personal report">
        <h2 className="solar-section-title">Personal</h2>
        <p className="mt-3 rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-sm text-[var(--muted)]">
          Personal report is unavailable for this month. Save a snapshot on{" "}
          <Link href="/finance/personal" className="underline underline-offset-2">
            Personal
          </Link>{" "}
          or{" "}
          <Link href="/finance/import" className="underline underline-offset-2">
            import a statement
          </Link>
          .
        </p>
      </section>
    );
  }

  const hasFlow =
    report.income_gbp != null || report.spending_gbp != null || report.surplus_gbp != null;
  const showPension = report.pension_gbp !== 0;
  const showProperty = (report.property_gbp ?? 0) !== 0;
  const categories = report.spending_by_category ?? [];
  const expenses = report.largest_expenses ?? [];
  const debts = report.debts ?? [];

  return (
    <section className="space-y-4" aria-label="Personal report">
      <div>
        <h2 className="solar-section-title">Personal</h2>
        {report.flow_note ? (
          <p className="mt-1 text-sm text-[var(--muted)]">{report.flow_note}</p>
        ) : null}
      </div>

      {report.empty_state ? (
        <p className="rounded-xl border border-dashed border-[var(--border)] px-4 py-4 text-sm text-[var(--muted)]">
          {report.empty_state}{" "}
          <Link href="/finance/personal" className="underline underline-offset-2">
            Open Personal
          </Link>
          {" · "}
          <Link href="/finance/import" className="underline underline-offset-2">
            Import a statement
          </Link>
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {hasFlow ? (
          <>
            <MetricTile
              label="Income"
              value={report.income_gbp}
              hint={changeHint(report.income_change_gbp, report.previous_month_income_gbp)}
            />
            <MetricTile
              label="Spending"
              value={report.spending_gbp}
              warning={report.spending_gbp != null && report.spending_gbp > 0}
              hint={changeHint(report.spending_change_gbp, report.previous_month_spending_gbp)}
            />
            <MetricTile
              label="Surplus"
              value={report.surplus_gbp}
              positive={report.surplus_gbp != null && report.surplus_gbp > 0}
              warning={report.surplus_gbp != null && report.surplus_gbp < 0}
            />
          </>
        ) : null}
        <MetricTile label="Personal cash" value={report.cash_gbp} />
        <MetricTile
          label="Personal debt"
          value={report.debt_gbp}
          warning={report.debt_gbp > 0}
        />
        {showPension ? <MetricTile label="Pension" value={report.pension_gbp} /> : null}
        {showProperty ? <MetricTile label="Property" value={report.property_gbp} /> : null}
        <MetricTile
          label="Personal net worth"
          value={report.net_worth_gbp}
          positive={report.net_worth_gbp > 0}
        />
        {report.household_bills_gbp != null ? (
          <MetricTile label="Household bills" value={report.household_bills_gbp} />
        ) : null}
        {report.debt_repayments_gbp != null ? (
          <MetricTile label="Debt repayments" value={report.debt_repayments_gbp} />
        ) : null}
      </div>

      {categories.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold">Spending by category</h3>
          <div className="mt-3 overflow-x-auto rounded-2xl border border-[var(--border)]">
            <table className="min-w-[420px] w-full text-sm">
              <caption className="sr-only">Personal spending by category</caption>
              <thead>
                <tr className="border-b border-[var(--border)] text-left text-xs uppercase tracking-wide text-[var(--muted)]">
                  <th className="px-4 py-3">Category</th>
                  <th className="px-4 py-3">Amount</th>
                  <th className="px-4 py-3">Transactions</th>
                </tr>
              </thead>
              <tbody>
                {categories.map((row) => (
                  <tr key={row.category} className="border-b border-[var(--border)]">
                    <td className="px-4 py-3">{row.category}</td>
                    <td className="px-4 py-3 tabular-nums">{formatGbp(row.amount_gbp)}</td>
                    <td className="px-4 py-3 tabular-nums text-[var(--muted)]">
                      {row.transaction_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {expenses.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold">Largest expenses</h3>
          <ul className="mt-3 space-y-2">
            {expenses.map((item) => (
              <li
                key={item.id}
                className="flex items-start justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm"
              >
                <span>
                  <span className="font-medium">{item.description || item.category}</span>
                  <span className="mt-0.5 block text-xs text-[var(--muted)]">
                    {item.posted_on}
                    {item.category ? ` · ${item.category}` : ""}
                    {item.account_name ? ` · ${item.account_name}` : ""}
                  </span>
                </span>
                <span className="shrink-0 font-semibold tabular-nums">
                  {formatGbp(item.amount_gbp)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {debts.length > 0 ? (
        <div>
          <h3 className="text-sm font-semibold">Personal debts</h3>
          <ul className="mt-3 space-y-2">
            {debts.map((debt) => (
              <li
                key={debt.id}
                className="flex items-center justify-between gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-3 text-sm"
              >
                <span>
                  {debt.name}
                  <span className="ml-2 text-[var(--muted)]">
                    {debt.debt_type.replaceAll("_", " ")}
                    {debt.interest_rate_known
                      ? ` · ${debt.interest_rate_pct.toFixed(1)}% APR`
                      : " · APR unknown"}
                  </span>
                </span>
                <span className="font-semibold tabular-nums">{formatGbp(debt.balance_gbp)}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
