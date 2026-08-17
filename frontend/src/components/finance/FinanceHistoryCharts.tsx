"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { FinanceReports } from "@/lib/finance-schemas";
import { formatGbp, formatMonthLabel } from "@/lib/money";

type FinanceHistoryChartsProps = {
  reports: FinanceReports;
};

function gbpTick(value: number) {
  return formatGbp(value, 0);
}

export function FinanceHistoryCharts({ reports }: FinanceHistoryChartsProps) {
  const cashflow = reports.cashflow_history.map((point) => ({
    ...point,
    label: formatMonthLabel(point.month),
  }));
  const debt = reports.debt_history.map((point) => ({
    ...point,
    label: formatMonthLabel(point.month),
  }));

  if (cashflow.length === 0 && debt.length < 2) {
    return (
      <p className="rounded-xl border border-dashed border-[var(--border)] px-4 py-6 text-sm text-[var(--muted)]">
        No snapshot history yet. Save a monthly snapshot on Personal to start a cashflow chart.
        Debt reduction appears after a second month has been recorded.
      </p>
    );
  }

  return (
    <div className="space-y-6">
      {cashflow.length > 0 ? (
        <section>
          <h3 className="text-sm font-semibold">Personal cashflow by month</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">
            From saved snapshots only — one point per month, latest snapshot wins.
          </p>
          <div className="mt-3 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={cashflow} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={gbpTick} />
                <Tooltip
                  formatter={(value) => (typeof value === "number" ? formatGbp(value) : "—")}
                />
                <Legend />
                <Bar dataKey="income_gbp" name="Income" fill="#059669" radius={[4, 4, 0, 0]} />
                <Bar dataKey="spending_gbp" name="Spending" fill="#d97706" radius={[4, 4, 0, 0]} />
                <Bar dataKey="surplus_gbp" name="Surplus" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
      {debt.length >= 2 ? (
        <section>
          <h3 className="text-sm font-semibold">Recorded total debt</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Months the app has actually recorded. No invented points.
          </p>
          <div className="mt-3 h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={debt} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} tickFormatter={gbpTick} />
                <Tooltip
                  formatter={(value) => (typeof value === "number" ? formatGbp(value) : "—")}
                />
                <Line
                  type="monotone"
                  dataKey="total_debt_gbp"
                  name="Total debt"
                  stroke="#b45309"
                  strokeWidth={2}
                  dot
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
    </div>
  );
}
