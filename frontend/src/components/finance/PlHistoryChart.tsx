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

import { formatGbp } from "@/lib/money";

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

  const chartData = points.map((p) => ({
    month: p.month.slice(2),
    turnover: p.turnover_gbp,
    expenses: p.expenses_gbp,
    profit: p.profit_gbp,
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
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              formatter={(value) =>
                typeof value === "number" ? formatGbp(value) : String(value ?? "")
              }
            />
            <Legend />
            <Bar dataKey="turnover" name="Turnover" fill="var(--accent-solar, #f59e0b)" radius={[4, 4, 0, 0]} />
            <Bar dataKey="expenses" name="Expenses" fill="var(--muted)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
            <XAxis dataKey="month" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip
              formatter={(value) =>
                typeof value === "number" ? formatGbp(value) : String(value ?? "")
              }
            />
            <Line
              type="monotone"
              dataKey="profit"
              name="Profit"
              stroke="var(--accent-battery, #10b981)"
              strokeWidth={2}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
