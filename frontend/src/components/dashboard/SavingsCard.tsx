"use client";

import type { LiveMetrics, MetricSummary } from "@/lib/schemas";
import { selfConsumptionPctFromLive } from "@/lib/energy-flow";
import { formatCurrencyAmount, formatSavings, SAVINGS_EXPLAINER } from "@/lib/money";

type SavingsCardProps = {
  summary: MetricSummary | null;
  live?: LiveMetrics | null;
  loading?: boolean;
  compact?: boolean;
};

function formatCurrency(value: number, currency: string) {
  return formatCurrencyAmount(value, currency);
}

function StatTile({
  label,
  value,
  highlight,
  sub,
}: {
  label: string;
  value: string;
  highlight?: "positive" | "neutral";
  sub?: string;
}) {
  return (
    <div className="solar-panel bg-[var(--surface)] p-4">
      <p className="solar-eyebrow">{label}</p>
      <p
        className={`mt-1.5 text-2xl font-bold tracking-tight tabular-nums ${
          highlight === "positive"
            ? "text-emerald-600 dark:text-emerald-400"
            : highlight === "neutral"
              ? "text-[var(--foreground)]"
              : ""
        }`}
      >
        {value}
      </p>
      {sub ? <p className="mt-0.5 text-xs text-[var(--muted)]">{sub}</p> : null}
    </div>
  );
}

export function SavingsCard({ summary, live = null, loading, compact = false }: SavingsCardProps) {
  if (loading) {
    return (
      <section className="solar-card solar-skeleton">
        <div className="h-6 w-40 rounded bg-[var(--border)]" />
        <div className="mt-6 h-20 rounded-xl bg-[var(--border)]" />
      </section>
    );
  }

  if (!summary) {
    return (
      <section className="solar-card">
        <h2 className="solar-section-title">Savings &amp; cost</h2>
        <div className="mt-4 flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-[var(--surface-sunken)] px-6 py-10 text-center">
          <p className="text-sm font-medium text-[var(--foreground)]">No summary data yet</p>
          <p className="mt-1 max-w-sm text-sm text-[var(--muted)]">
            Samples accumulate as the backend sampler runs. Check back after a few minutes.
          </p>
        </div>
      </section>
    );
  }

  const isCredit = summary.net_cost < 0;
  const savingsDisplay = formatSavings(summary.savings, summary.currency);
  const pvKwh = live?.daily_pv_kwh ?? summary.pv_kwh;
  const importKwh = live?.daily_import_kwh ?? summary.import_kwh;
  const exportKwh = live?.daily_export_kwh ?? summary.export_kwh;
  const selfConsumedPct = live ? selfConsumptionPctFromLive(live) : summary.self_consumption_pct;

  return (
    <section className="solar-card overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="solar-section-title">
            {compact ? "Today's savings" : "Savings & cost"}
          </h2>
          <p className="mt-0.5 text-sm text-[var(--muted)]">
            {summary.range.charAt(0).toUpperCase() + summary.range.slice(1)} range · current tariff
          </p>
        </div>
        {!compact ? (
          <span className="solar-status-pill text-emerald-600 dark:text-emerald-400">
            {selfConsumedPct.toFixed(0)}% self-consumed
          </span>
        ) : null}
      </div>

      {/* Hero savings figure */}
      <div
        className="mt-5 rounded-xl border border-[var(--border)] p-5 sm:p-6"
        style={{
          background:
            "linear-gradient(135deg, color-mix(in srgb, var(--accent-battery) 12%, var(--surface-elevated)), var(--surface-elevated))",
        }}
      >
        <p className="solar-eyebrow">Estimated savings</p>
        <p className={`mt-1 text-4xl font-bold tracking-tight tabular-nums sm:text-5xl ${savingsDisplay.className}`}>
          {savingsDisplay.amount}
        </p>
        <p className="mt-2 text-sm font-medium text-[var(--foreground)]">{savingsDisplay.headline}</p>
        <p className="mt-1 text-sm text-[var(--muted)]">
          vs {formatCurrency(summary.estimated_cost_without_solar, summary.currency)} without solar
        </p>
        <p className="mt-2 text-xs text-[var(--muted)]">{SAVINGS_EXPLAINER}</p>
      </div>

      <div className={`mt-4 grid gap-3 ${compact ? "grid-cols-2" : "sm:grid-cols-2 lg:grid-cols-4"}`}>
        {!compact ? (
          <>
            <StatTile
              label="Net cost"
              value={
                isCredit
                  ? `+${formatCurrency(summary.net_cost, summary.currency)} credit`
                  : formatCurrency(summary.net_cost, summary.currency)
              }
              highlight="neutral"
              sub={isCredit ? "You earned more than you spent" : "Import minus export credit"}
            />
            <StatTile
              label="Self-consumed"
              value={`${selfConsumedPct.toFixed(1)}%`}
              sub="Of PV generation used on-site"
            />
            <StatTile
              label="Import cost"
              value={formatCurrency(summary.import_cost, summary.currency)}
              sub={`${importKwh.toFixed(1)} kWh imported`}
            />
            <StatTile
              label="Export credit"
              value={formatCurrency(summary.export_credit, summary.currency)}
              sub={`${exportKwh.toFixed(1)} kWh exported`}
            />
          </>
        ) : (
          <>
            <StatTile
              label="Net cost"
              value={formatCurrency(summary.net_cost, summary.currency)}
              highlight="neutral"
            />
            <StatTile
              label="Self-consumed"
              value={`${selfConsumedPct.toFixed(0)}%`}
            />
          </>
        )}
      </div>

      {!compact ? (
        <dl className="mt-5 grid gap-x-6 gap-y-2 border-t border-[var(--border)] pt-4 text-sm sm:grid-cols-2">
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--muted)]">PV generated</dt>
            <dd className="font-semibold tabular-nums">{pvKwh.toFixed(1)} kWh</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--muted)]">Consumption</dt>
            <dd className="font-semibold tabular-nums">{summary.consumption_kwh.toFixed(1)} kWh</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--muted)]">Grid import</dt>
            <dd className="font-semibold tabular-nums">{importKwh.toFixed(1)} kWh</dd>
          </div>
          <div className="flex justify-between gap-4">
            <dt className="text-[var(--muted)]">Grid export</dt>
            <dd className="font-semibold tabular-nums">{exportKwh.toFixed(1)} kWh</dd>
          </div>
        </dl>
      ) : null}
    </section>
  );
}
