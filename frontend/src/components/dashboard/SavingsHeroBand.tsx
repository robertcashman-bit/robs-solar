"use client";

import Link from "next/link";

import type { LiveMetrics, MetricSummary, ChargeWindowStatus } from "@/lib/schemas";
import { deriveHouseLoadDisplay, gridHeroLabel, resolveBatteryPower, selfConsumptionPctFromLive } from "@/lib/energy-flow";
import { formatSavings, SAVINGS_EXPLAINER } from "@/lib/money";
import {
  ArrowDownIcon,
  ArrowUpIcon,
  BatteryIcon,
  BoltIcon,
  ChartIcon,
  GaugeIcon,
} from "@/components/shared/icons";

type SavingsHeroBandProps = {
  metrics: LiveMetrics;
  summary: MetricSummary | null;
  evCharging?: boolean;
  chargeWindow?: ChargeWindowStatus | null;
};

const HIGH_GRID_DRAW_W = 4000;

const toneClasses = {
  export: "from-violet-500/20 to-violet-600/5 border-violet-400/30 text-violet-700 dark:text-violet-300",
  import: "from-rose-500/20 to-rose-600/5 border-rose-400/30 text-rose-700 dark:text-rose-300",
  neutral: "from-zinc-500/10 to-zinc-600/5 border-[var(--border)] text-[var(--muted)]",
  savings: "from-emerald-500/25 to-emerald-600/5 border-emerald-400/35 text-emerald-700 dark:text-emerald-300",
  battery: "from-emerald-500/20 to-teal-600/5 border-emerald-400/30 text-emerald-700 dark:text-emerald-300",
  pv: "from-amber-500/25 to-orange-600/5 border-amber-400/35 text-amber-800 dark:text-amber-300",
};

export function SavingsHeroBand({
  metrics,
  summary,
  evCharging = false,
  chargeWindow = null,
}: SavingsHeroBandProps) {
  const grid = gridHeroLabel(metrics);
  const houseLoad = deriveHouseLoadDisplay(metrics, resolveBatteryPower(metrics));
  const showEvBadge =
    evCharging || (Boolean(chargeWindow?.cheap_now) && metrics.grid_import_w > HIGH_GRID_DRAW_W);
  const showGridDraw = metrics.grid_import_w > HIGH_GRID_DRAW_W;
  const selfPct = selfConsumptionPctFromLive(metrics);
  const savingsToday = summary?.savings ?? 0;
  const currency = summary?.currency ?? "GBP";
  const savingsDisplay = formatSavings(savingsToday, currency);

  return (
    <section aria-label="Savings control centre KPIs" className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="solar-eyebrow">Savings control centre</p>
          <h2 className="text-xl font-bold tracking-tight sm:text-2xl">
            {summary ? (
              <span className={savingsDisplay.className}>{savingsDisplay.headline}</span>
            ) : (
              <span>Today&apos;s energy snapshot</span>
            )}
          </h2>
          {summary ? (
            <p className="mt-1 max-w-xl text-xs text-[var(--muted)]">{SAVINGS_EXPLAINER}</p>
          ) : null}
        </div>
        <Link href="/analytics" className="solar-btn-ghost text-xs sm:text-sm">
          Full analytics →
        </Link>
        {showEvBadge ? (
          <span className="rounded-full border border-emerald-400/40 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-700 dark:text-emerald-300">
            EV charging (cheap window)
          </span>
        ) : null}
        {showGridDraw ? (
          <span className="rounded-full border border-rose-400/40 bg-rose-500/10 px-3 py-1 text-xs font-medium text-rose-800 dark:text-rose-300">
            Grid draw {Math.round(metrics.grid_import_w).toLocaleString()} W
          </span>
        ) : null}
      </div>

      <div className="-mx-1 flex gap-3 overflow-x-auto px-1 pb-1 snap-x snap-mandatory sm:mx-0 sm:grid sm:grid-cols-2 sm:overflow-visible sm:pb-0 lg:grid-cols-5">
        <article
          className={`hero-kpi relative min-w-[72%] shrink-0 snap-start overflow-hidden rounded-2xl border bg-gradient-to-br p-4 sm:min-w-0 ${
            savingsDisplay.tone === "negative"
              ? "from-amber-500/20 to-amber-600/5 border-amber-400/30 text-amber-800 dark:text-amber-300"
              : toneClasses.savings
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-[0.65rem] font-semibold uppercase tracking-wider opacity-80">
                Est. savings
              </p>
              <p className={`mt-1 text-2xl font-bold tabular-nums tracking-tight ${savingsDisplay.className}`}>
                {summary ? savingsDisplay.amount : "—"}
              </p>
              <p className="mt-0.5 text-xs opacity-75">{summary ? savingsDisplay.sublabel : "vs no solar"}</p>
            </div>
            <ChartIcon size={22} className="opacity-70" />
          </div>
        </article>

        <article
          className={`hero-kpi relative min-w-[72%] shrink-0 snap-start overflow-hidden rounded-2xl border bg-gradient-to-br p-4 sm:min-w-0 ${toneClasses.battery}`}
        >
          <p className="text-[0.65rem] font-semibold uppercase tracking-wider opacity-80">Battery</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{metrics.battery_soc_pct.toFixed(0)}%</p>
          <p className="mt-0.5 text-xs opacity-75">
            {metrics.battery_power_w != null && Math.abs(metrics.battery_power_w) > 50
              ? `${metrics.battery_power_w > 0 ? "Discharging" : "Charging"} ${Math.round(Math.abs(metrics.battery_power_w))} W`
              : "Idle"}
          </p>
          <div className="mt-2 h-1 overflow-hidden rounded-full bg-black/10 dark:bg-white/10">
            <div
              className="h-full rounded-full bg-emerald-500 transition-all duration-700"
              style={{ width: `${metrics.battery_soc_pct}%` }}
            />
          </div>
        </article>

        <article
          className={`hero-kpi relative min-w-[72%] shrink-0 snap-start overflow-hidden rounded-2xl border bg-gradient-to-br p-4 sm:min-w-0 ${toneClasses[grid.tone]}`}
        >
          <p className="text-[0.65rem] font-semibold uppercase tracking-wider opacity-80">Grid now</p>
          <p className="mt-1 text-lg font-bold leading-tight">{grid.text}</p>
          <p className="mt-0.5 text-xs opacity-75 capitalize">
            {metrics.inverter_mode.replaceAll("_", " ")} mode
          </p>
        </article>

        <article
          className={`hero-kpi relative min-w-[72%] shrink-0 snap-start overflow-hidden rounded-2xl border bg-gradient-to-br p-4 sm:min-w-0 ${toneClasses.pv}`}
        >
          <p className="text-[0.65rem] font-semibold uppercase tracking-wider opacity-80">Solar now</p>
          <p className="mt-1 text-2xl font-bold tabular-nums">
            {Math.round(metrics.pv_power_w).toLocaleString()} W
          </p>
          <p className="mt-0.5 text-xs opacity-75">{metrics.daily_pv_kwh.toFixed(1)} kWh today</p>
        </article>

        <article className="hero-kpi relative min-w-[72%] shrink-0 snap-start overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-4 sm:col-span-2 sm:min-w-0 lg:col-span-1">
          <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--muted)]">
            Self-consumed
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums">{selfPct.toFixed(0)}%</p>
          <p className="mt-0.5 text-xs text-[var(--muted)]">Of PV used on-site</p>
        </article>
      </div>

      <div className="flex flex-wrap gap-2 text-xs">
        <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1">
          <BoltIcon size={12} className="text-amber-500" />
          Load {houseLoad.isMinimal ? "Minimal" : houseLoad.value}
          {houseLoad.sublabel && !houseLoad.isMinimal ? ` · ${houseLoad.sublabel}` : null}
          {houseLoad.isMinimal && houseLoad.sublabel ? ` · ${houseLoad.sublabel}` : null}
        </span>
        <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1">
          <BatteryIcon size={12} className="text-emerald-500" />
          {metrics.daily_battery_charge_kwh != null
            ? `+${metrics.daily_battery_charge_kwh.toFixed(1)} kWh charged today`
            : "Battery active"}
        </span>
        {showGridDraw ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-rose-400/40 bg-rose-500/15 px-2.5 py-1 font-medium text-rose-800 dark:text-rose-300">
            <ArrowDownIcon size={12} />
            Grid draw {Math.round(metrics.grid_import_w).toLocaleString()} W
          </span>
        ) : null}
        {metrics.grid_import_w > 0 && !showGridDraw ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-rose-400/30 bg-rose-500/10 px-2.5 py-1 text-rose-800 dark:text-rose-300">
            <ArrowDownIcon size={12} />
            {metrics.daily_import_kwh.toFixed(1)} kWh imported
          </span>
        ) : null}
        {metrics.grid_export_w > 0 ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-violet-400/30 bg-violet-500/10 px-2.5 py-1 text-violet-800 dark:text-violet-300">
            <ArrowUpIcon size={12} />
            {metrics.daily_export_kwh.toFixed(1)} kWh exported
          </span>
        ) : null}
        <span className="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 capitalize">
          <GaugeIcon size={12} />
          {metrics.inverter_status}
        </span>
      </div>
    </section>
  );
}
