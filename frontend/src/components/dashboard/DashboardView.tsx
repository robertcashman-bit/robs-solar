import { useMemo } from "react";

import type {
  ChargeWindowStatus,
  ConnectivityStatus,
  LiveMetrics,
  MetricCompare,
  MetricSummary,
  OctopusRatePlan,
  OctopusTariff,
  SellOpportunity,
} from "@/lib/schemas";
import { buildSavingsInsights } from "@/lib/savings-insights";

import { ArrowDownIcon, ArrowUpIcon, BoltIcon, ChartIcon } from "@/components/shared/icons";

import { CheapWindowBanner } from "./CheapWindowBanner";
import { OctopusRatesCard } from "./OctopusRatesCard";
import { SellOpportunityCard } from "./SellOpportunityCard";
import { EnergyFlow } from "./EnergyFlow";
import { FreshnessLabel } from "./FreshnessLabel";
import { LiveDetailCards } from "./LiveDetailCards";
import { MetricCard, MetricCardSkeleton } from "./MetricCard";
import { QuickActionsStrip } from "./QuickActionsStrip";
import { SavingsHeroBand } from "./SavingsHeroBand";
import { SavingsInsightsPanel } from "./SavingsInsightsPanel";
import { SavingsCard } from "./SavingsCard";
import { AiAdviceCard } from "./AiAdviceCard";
import { TodayCompareStrip } from "./TodayCompareStrip";
import type { CompareRange } from "@/lib/money";

type DashboardViewProps = {
  metrics: LiveMetrics | null;
  connectivity: ConnectivityStatus | null;
  summary: MetricSummary | null;
  compare: MetricCompare | null;
  compareRange?: CompareRange;
  onCompareRangeChange?: (range: CompareRange) => void;
  loading: boolean;
  error: string | null;
  readOnly: boolean;
  octopusTariff?: OctopusTariff | null;
  agilePricePence?: number | null;
  evCharging?: boolean;
  chargeWindow?: ChargeWindowStatus | null;
  ratePlan?: OctopusRatePlan | null;
  sellOpportunity?: SellOpportunity | null;
  canControl?: boolean;
  onRefresh?: () => void | Promise<void>;
};

function StatusPill({
  dotColor,
  pulse,
  children,
}: {
  dotColor: string;
  pulse?: boolean;
  children: React.ReactNode;
}) {
  return (
    <span className="solar-status-pill">
      <span
        className={`solar-status-dot ${dotColor} ${pulse ? "solar-dot-live" : ""}`}
        style={pulse ? { background: "currentColor" } : undefined}
      />
      {children}
    </span>
  );
}

function selfSufficiencyPct(metrics: LiveMetrics): number {
  if (metrics.daily_pv_kwh <= 0) {
    return 0;
  }
  const selfConsumed = Math.max(0, metrics.daily_pv_kwh - metrics.daily_export_kwh);
  return Math.min(100, (selfConsumed / metrics.daily_pv_kwh) * 100);
}

export function DashboardView({
  metrics,
  connectivity,
  summary,
  compare,
  compareRange = "day",
  onCompareRangeChange = () => {},
  loading,
  error,
  readOnly,
  octopusTariff = null,
  agilePricePence = null,
  evCharging = false,
  chargeWindow = null,
  ratePlan = null,
  sellOpportunity = null,
  canControl = false,
  onRefresh,
}: DashboardViewProps) {
  const insights = useMemo(
    () =>
      metrics
        ? buildSavingsInsights(metrics, summary, {
            importRatePence: octopusTariff?.import_rate_pence ?? null,
            exportRatePence: octopusTariff?.export_rate_pence ?? null,
            tariffFamily: octopusTariff?.tariff_family ?? null,
            agilePricePence,
          })
        : [],
    [metrics, summary, octopusTariff, agilePricePence],
  );

  if (loading) {
    return (
      <section aria-label="Live dashboard loading" className="space-y-4">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <MetricCardSkeleton key={index} />
          ))}
        </div>
        <div className="solar-skeleton min-h-[280px] rounded-2xl" />
        <div className="solar-skeleton min-h-[200px] rounded-2xl" />
      </section>
    );
  }

  if (error) {
    return (
      <div
        role="alert"
        className="rounded-xl border border-red-300/50 bg-red-50/80 px-4 py-3 text-red-800 dark:bg-red-950/40 dark:text-red-300"
      >
        {error}
      </div>
    );
  }

  if (!metrics) {
    return (
      <div className="solar-card text-center text-[var(--muted)]">
        <p className="font-medium text-[var(--foreground)]">No live metrics yet</p>
        <p className="mt-1 text-sm">Waiting for the first poll from your inverter adapter.</p>
      </div>
    );
  }

  const isSimulated = (connectivity?.adapter_mode ?? "simulator") === "simulator";
  const connected = connectivity?.adapter_connected ?? false;
  const selfSufficiency = selfSufficiencyPct(metrics);

  return (
    <div className="space-y-6">
      <CheapWindowBanner status={chargeWindow} />
      <OctopusRatesCard plan={ratePlan} />
      <SellOpportunityCard
        opportunity={sellOpportunity}
        canControl={canControl}
        onRefresh={onRefresh}
      />
      <div className="flex flex-wrap items-center gap-2">
        <StatusPill dotColor={isSimulated ? "bg-sky-400" : "bg-violet-400"} pulse={!isSimulated}>
          {isSimulated ? "Simulated data" : "Live data"}
        </StatusPill>
        <StatusPill dotColor={connected ? "bg-emerald-400" : "bg-amber-400"} pulse={connected}>
          {connected ? "Connected" : "Degraded"}
        </StatusPill>
        <StatusPill dotColor={readOnly ? "bg-zinc-400" : "bg-emerald-400"}>
          {readOnly ? "Read-only" : "Writes enabled"}
        </StatusPill>
        {metrics.inverter_status === "fault" ? (
          <StatusPill dotColor="bg-rose-500">Inverter fault</StatusPill>
        ) : metrics.inverter_status === "offline" ? (
          <StatusPill dotColor="bg-amber-500">Inverter offline</StatusPill>
        ) : null}
        {octopusTariff?.import_rate_pence != null ? (
          <StatusPill dotColor="bg-amber-400">
            {octopusTariff.tariff_family === "IOG" ? "IOG" : "Import"}:{" "}
            {octopusTariff.import_rate_pence.toFixed(1)}p/kWh
          </StatusPill>
        ) : agilePricePence != null ? (
          <StatusPill dotColor="bg-amber-400">
            Agile now: {agilePricePence.toFixed(1)}p/kWh
          </StatusPill>
        ) : null}
        {octopusTariff?.export_rate_pence != null ? (
          <StatusPill dotColor="bg-sky-400">
            Export: {octopusTariff.export_rate_pence.toFixed(1)}p/kWh
          </StatusPill>
        ) : null}
      </div>

      <SavingsHeroBand metrics={metrics} summary={summary} evCharging={evCharging} />
      <TodayCompareStrip
        compare={compare}
        range={compareRange}
        onRangeChange={onCompareRangeChange}
      />
      <AiAdviceCard canControl={canControl} />
      <QuickActionsStrip />
      <SavingsInsightsPanel insights={insights} />

      <EnergyFlow metrics={metrics} />

      <SavingsCard summary={summary} />

      <section aria-label="Live dashboard" className="space-y-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div className="flex items-baseline gap-3">
            <h3 className="solar-section-title">Today</h3>
            <FreshnessLabel timestamp={metrics.timestamp} />
          </div>
          <p className="text-sm text-[var(--muted)]">
            Inverter:{" "}
            <span className="font-medium capitalize text-[var(--foreground)]">
              {metrics.inverter_mode.replaceAll("_", " ")}
            </span>
          </p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            label="Daily PV"
            value={`${metrics.daily_pv_kwh.toFixed(1)} kWh`}
            icon={<BoltIcon size={20} />}
            accent="pv"
            animationDelay={0}
          />
          <MetricCard
            label="Daily import"
            value={`${metrics.daily_import_kwh.toFixed(1)} kWh`}
            icon={<ArrowDownIcon size={20} />}
            accent="import"
            animationDelay={50}
          />
          <MetricCard
            label="Daily export"
            value={`${metrics.daily_export_kwh.toFixed(1)} kWh`}
            icon={<ArrowUpIcon size={20} />}
            accent="export"
            animationDelay={100}
          />
          <MetricCard
            label="Self-sufficiency"
            value={`${selfSufficiency.toFixed(1)}%`}
            hint="PV used on-site vs exported today"
            icon={<ChartIcon size={20} />}
            accent="battery"
            progress={selfSufficiency}
            animationDelay={150}
          />
        </div>
      </section>

      <details className="solar-card group">
        <summary className="cursor-pointer list-none font-semibold marker:content-none">
          <span className="flex items-center justify-between gap-2">
            Advanced live readings
            <span className="text-xs font-normal text-[var(--muted)] group-open:hidden">
              Tap to expand
            </span>
          </span>
        </summary>
        <div className="mt-4">
          <LiveDetailCards metrics={metrics} />
        </div>
      </details>
    </div>
  );
}
