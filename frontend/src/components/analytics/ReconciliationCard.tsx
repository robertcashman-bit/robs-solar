"use client";

import type { HistoryRange, Reconciliation } from "@/lib/schemas";

type ReconciliationCardProps = {
  data: Reconciliation | null;
  range: HistoryRange;
  loading?: boolean;
};

function gbp(value: number, currency: string) {
  const sym = currency === "GBP" ? "£" : currency;
  return `${sym}${value.toFixed(2)}`;
}

export function ReconciliationCard({ data, range, loading }: ReconciliationCardProps) {
  if (loading) {
    return (
      <section className="solar-card">
        <h3 className="solar-section-title">Bill reconciliation</h3>
        <p className="text-sm text-[var(--muted)]">Loading meter data…</p>
      </section>
    );
  }

  if (!data?.configured) {
    return (
      <section className="solar-card">
        <h3 className="solar-section-title">Bill reconciliation</h3>
        <p className="text-sm text-[var(--muted)]">
          {data?.message || "Configure Octopus API in Settings to compare meter reads with inverter estimates."}
        </p>
      </section>
    );
  }

  return (
    <section className="solar-card space-y-4">
      <div>
        <h3 className="solar-section-title">Bill reconciliation</h3>
        <p className="text-sm text-[var(--muted)]">
          Octopus half-hourly meter import vs inverter savings estimate ({range}).
        </p>
      </div>
      <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
          <dt className="text-xs text-[var(--muted)]">Meter import</dt>
          <dd className="text-lg font-semibold tabular-nums">{data.meter_import_kwh.toFixed(1)} kWh</dd>
          <dd className="text-xs text-[var(--muted)]">
            Cheap {data.cheap_import_kwh.toFixed(1)} · Day {data.day_import_kwh.toFixed(1)}
          </dd>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
          <dt className="text-xs text-[var(--muted)]">Net bill impact</dt>
          <dd className="text-lg font-semibold tabular-nums">{gbp(data.net_bill_impact_gbp, data.currency)}</dd>
          <dd className="text-xs text-[var(--muted)]">
            Export credit {gbp(data.export_earnings_gbp, data.currency)}
          </dd>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
          <dt className="text-xs text-[var(--muted)]">Inverter estimate</dt>
          <dd className="text-lg font-semibold tabular-nums">{gbp(data.inverter_estimate_gbp, data.currency)}</dd>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3">
          <dt className="text-xs text-[var(--muted)]">Delta</dt>
          <dd
            className={`text-lg font-semibold tabular-nums ${
              Math.abs(data.delta_gbp) < 1
                ? "text-emerald-600 dark:text-emerald-400"
                : "text-amber-700 dark:text-amber-300"
            }`}
          >
            {gbp(data.delta_gbp, data.currency)}
          </dd>
        </div>
      </dl>
    </section>
  );
}
