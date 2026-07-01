"use client";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { MetricHistory, SavingsHistory } from "@/lib/schemas";

type SavingsHistoryChartsProps = {
  savingsHistory: SavingsHistory | null;
  metricHistory: MetricHistory | null;
  currency?: string;
};

export function SavingsHistoryCharts({
  savingsHistory,
  metricHistory,
  currency = "GBP",
}: SavingsHistoryChartsProps) {
  const savingsPoints =
    savingsHistory?.points.map((p) => ({
      date: p.date.slice(5),
      savings: p.savings_gbp,
      score: p.optimisation_score ?? 0,
    })) ?? [];

  const importByHour = new Map<number, number>();
  for (const point of metricHistory?.points ?? []) {
    const hour = new Date(point.timestamp).getHours();
    importByHour.set(hour, (importByHour.get(hour) ?? 0) + point.grid_import_w / 1000);
  }
  const importChart = Array.from(importByHour.entries())
    .sort(([a], [b]) => a - b)
    .map(([hour, kwh]) => ({ hour: `${hour}:00`, kwh: Number(kwh.toFixed(2)) }));

  const socChart =
    metricHistory?.points.map((p) => ({
      time: new Date(p.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      soc: p.battery_soc_pct,
      batteryKw: (p.battery_power_w ?? 0) / 1000,
    })) ?? [];

  return (
    <div className="space-y-6">
      {savingsPoints.length > 0 ? (
        <section className="solar-card">
          <h2 className="solar-section-title">Daily savings over time</h2>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={savingsPoints}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip
                  formatter={(v) =>
                    typeof v === "number"
                      ? [`${currency} ${v.toFixed(2)}`, "Saving"]
                      : ["", "Saving"]
                  }
                />
                <Bar dataKey="savings" fill="var(--accent-battery)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
          {savingsHistory ? (
            <p className="mt-2 text-sm text-[var(--muted)]">
              Total {currency} {savingsHistory.total_savings_gbp.toFixed(2)} · YTD{" "}
              {savingsHistory.year_to_date_gbp.toFixed(2)} · Projected annual{" "}
              {savingsHistory.projected_annual_gbp.toFixed(2)}
            </p>
          ) : null}
        </section>
      ) : null}

      {importChart.length > 0 ? (
        <section className="solar-card">
          <h2 className="solar-section-title">Grid import by time of day</h2>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={importChart}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="hour" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="kwh" fill="var(--accent-import)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}

      {socChart.length > 0 ? (
        <section className="solar-card">
          <h2 className="solar-section-title">Battery SOC &amp; charge/discharge</h2>
          <div className="mt-4 h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={socChart}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} hide />
                <YAxis yAxisId="soc" tick={{ fontSize: 11 }} domain={[0, 100]} />
                <YAxis yAxisId="kw" orientation="right" tick={{ fontSize: 11 }} />
                <Tooltip />
                <Line yAxisId="soc" type="monotone" dataKey="soc" stroke="var(--accent-battery)" dot={false} />
                <Line yAxisId="kw" type="monotone" dataKey="batteryKw" stroke="var(--accent-load)" dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      ) : null}
    </div>
  );
}
