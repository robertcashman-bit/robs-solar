"use client";

import type { ReactNode } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { HistoryRange, MetricHistory, MetricSummary } from "@/lib/schemas";

type AnalyticsChartsProps = {
  history: MetricHistory | null;
  summary: MetricSummary | null;
  range: HistoryRange;
  onRangeChange: (range: HistoryRange) => void;
  loading?: boolean;
};

const RANGE_OPTIONS: { value: HistoryRange; label: string }[] = [
  { value: "day", label: "Day" },
  { value: "week", label: "Week" },
  { value: "month", label: "Month" },
];

const CHART_COLORS = {
  pv: "#f59e0b",
  load: "#0ea5e9",
  import: "#f43f5e",
  export: "#8b5cf6",
  battery: "#10b981",
};

function formatTime(timestamp: string, range: HistoryRange) {
  const date = new Date(timestamp);
  if (range === "day") {
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }
  return date.toLocaleDateString([], { month: "short", day: "numeric" });
}

function ChartTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number; color?: string }>;
  label?: string;
}) {
  if (!active || !payload?.length) {
    return null;
  }
  return (
    <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-solid)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-[var(--muted)]">{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} className="flex items-center gap-2 tabular-nums">
          <span className="h-2 w-2 rounded-full" style={{ background: entry.color }} />
          <span>{entry.name}:</span>
          <span className="font-semibold">{entry.value?.toLocaleString()}</span>
        </p>
      ))}
    </div>
  );
}

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: ReactNode }) {
  return (
    <section className="solar-card">
      <h3 className="solar-section-title">{title}</h3>
      {subtitle ? <p className="mt-0.5 text-sm text-[var(--muted)]">{subtitle}</p> : null}
      <div className="mt-4 min-h-[220px]">{children}</div>
    </section>
  );
}

function EmptyChartState({ message }: { message: string }) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface-sunken)] px-6 text-center">
      <p className="text-sm font-medium text-[var(--foreground)]">No data for this range</p>
      <p className="mt-1 max-w-md text-sm text-[var(--muted)]">{message}</p>
    </div>
  );
}

export function AnalyticsCharts({
  history,
  summary,
  range,
  onRangeChange,
  loading,
}: AnalyticsChartsProps) {
  const chartData =
    history?.points.map((p) => ({
      ...p,
      label: formatTime(p.timestamp, range),
    })) ?? [];

  const donutData = summary
    ? [
        { name: "Self-consumed", value: summary.self_consumption_pct },
        { name: "Exported", value: Math.max(0, 100 - summary.self_consumption_pct) },
      ]
    : [];

  const hasSoh = chartData.some((p) => p.battery_soh_pct != null);

  if (loading) {
    return (
      <div className="space-y-4">
        <div className="solar-skeleton h-11 w-56 rounded-xl" />
        <div className="solar-skeleton min-h-[280px] rounded-2xl" />
        <div className="solar-skeleton min-h-[240px] rounded-2xl" />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div
        className="inline-flex gap-1 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-1 shadow-sm"
        role="tablist"
        aria-label="Time range"
      >
        {RANGE_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={range === opt.value}
            onClick={() => onRangeChange(opt.value)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-all ${
              range === opt.value
                ? "bg-gradient-to-r from-amber-500 to-orange-500 text-white shadow-sm"
                : "text-[var(--muted)] hover:bg-[var(--surface-elevated)] hover:text-[var(--foreground)]"
            }`}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {chartData.length === 0 ? (
        <EmptyChartState message="Historical samples accumulate as the backend sampler runs. Check back after a few minutes." />
      ) : (
        <>
          <ChartCard title="Power over time" subtitle="PV generation vs house load">
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="pvGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.pv} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={CHART_COLORS.pv} stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="loadGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.load} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={CHART_COLORS.load} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} unit=" W" axisLine={false} tickLine={false} width={56} />
                <Tooltip content={<ChartTooltip />} />
                <Area
                  type="monotone"
                  dataKey="pv_power_w"
                  name="PV"
                  stroke={CHART_COLORS.pv}
                  fill="url(#pvGrad)"
                  strokeWidth={2}
                  dot={false}
                />
                <Area
                  type="monotone"
                  dataKey="house_load_w"
                  name="Load"
                  stroke={CHART_COLORS.load}
                  fill="url(#loadGrad)"
                  strokeWidth={2}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>

          <ChartCard title="Battery SOC" subtitle="State of charge over time">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--muted)" }} unit="%" axisLine={false} tickLine={false} width={44} />
                <Tooltip content={<ChartTooltip />} />
                <Line
                  type="monotone"
                  dataKey="battery_soc_pct"
                  name="SOC"
                  stroke={CHART_COLORS.battery}
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 4, fill: CHART_COLORS.battery }}
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>

          {hasSoh ? (
            <ChartCard title="Battery health (SOH)" subtitle="State of health when reported by inverter">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "var(--muted)" }} unit="%" axisLine={false} tickLine={false} width={44} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line
                    type="monotone"
                    dataKey="battery_soh_pct"
                    name="SOH"
                    stroke={CHART_COLORS.battery}
                    strokeWidth={2.5}
                    dot={false}
                    connectNulls
                  />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>
          ) : null}

          <ChartCard title="Grid import / export" subtitle="Grid exchange power">
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="importGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.import} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={CHART_COLORS.import} stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="exportGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={CHART_COLORS.export} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={CHART_COLORS.export} stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--border)" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 11, fill: "var(--muted)" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "var(--muted)" }} unit=" W" axisLine={false} tickLine={false} width={56} />
                <Tooltip content={<ChartTooltip />} />
                <Area
                  type="monotone"
                  dataKey="grid_import_w"
                  name="Import"
                  stroke={CHART_COLORS.import}
                  fill="url(#importGrad)"
                  strokeWidth={2}
                  dot={false}
                />
                <Area
                  type="monotone"
                  dataKey="grid_export_w"
                  name="Export"
                  stroke={CHART_COLORS.export}
                  fill="url(#exportGrad)"
                  strokeWidth={2}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </ChartCard>
        </>
      )}

      {summary && donutData.length > 0 ? (
        <ChartCard title="Self-consumption" subtitle="Share of PV used on-site vs exported">
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie
                data={donutData}
                dataKey="value"
                nameKey="name"
                cx="50%"
                cy="50%"
                innerRadius={58}
                outerRadius={82}
                paddingAngle={3}
                label={({ name, value }) => `${name}: ${value.toFixed(0)}%`}
              >
                <Cell fill={CHART_COLORS.battery} />
                <Cell fill={CHART_COLORS.export} />
              </Pie>
              <Tooltip content={<ChartTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      ) : null}
    </div>
  );
}
