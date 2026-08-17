"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatGbp, formatMonthLabel } from "@/lib/money";

export type PlHistoryPoint = {
  month: string;
  turnover_gbp: number;
  expenses_gbp: number;
  profit_gbp: number;
};

type PlHistoryChartProps = {
  points: PlHistoryPoint[];
};

export function PlHistoryChart({ points }: PlHistoryChartProps) {
  if (points.length === 0) {
    return (
      <p className="text-sm text-[var(--muted)]">
        No monthly P&amp;L snapshots yet. Save a business snapshot to build history.
      </p>
    );
  }

  const chartData = points.map((point) => ({
    month: formatMonthLabel(point.month),
    turnover: point.turnover_gbp,
    expenses: point.expenses_gbp,
    profit: point.profit_gbp,
  }));
  const latest = points[points.length - 1];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <p className="text-xs text-[var(--muted)]">Turnover ({latest.month})</p>
          <p className="text-lg font-semibold tabular-nums">{formatGbp(latest.turnover_gbp)}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--muted)]">Expenses</p>
          <p className="text-lg font-semibold tabular-nums">{formatGbp(latest.expenses_gbp)}</p>
        </div>
        <div>
          <p className="text-xs text-[var(--muted)]">Profit</p>
          <p className="text-lg font-semibold tabular-nums">{formatGbp(latest.profit_gbp)}</p>
        </div>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} tickFormatter={(value: number) => formatGbp(value, 0)} />
            <Tooltip formatter={(value) => (typeof value === "number" ? formatGbp(value) : "—")} />
            <Legend />
            <Bar dataKey="turnover" name="Turnover" fill="#059669" radius={[4, 4, 0, 0]} />
            <Bar dataKey="expenses" name="Expenses" fill="#d97706" radius={[4, 4, 0, 0]} />
            <Bar dataKey="profit" name="Profit" fill="#2563eb" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
