import type { OctopusRatePlan } from "@/lib/schemas";
import { formatLocalTime, formatWindowRange } from "@/lib/tariff-time";

import { ChartIcon } from "@/components/shared/icons";

type OctopusRatesCardProps = {
  plan: OctopusRatePlan | null;
};

function tariffTitle(family: string, displayName: string): string {
  if (displayName.trim()) {
    return displayName;
  }
  if (family === "IOG") {
    return "Intelligent Octopus Go";
  }
  if (family === "AGILE") {
    return "Octopus Agile";
  }
  return "Your import tariff";
}

export function OctopusRatesCard({ plan }: OctopusRatesCardProps) {
  if (!plan?.configured) {
    return null;
  }

  const hasCheapTier =
    plan.cheap_rate_pence != null &&
    plan.peak_rate_pence != null &&
    plan.cheap_rate_pence !== plan.peak_rate_pence;

  return (
    <section
      aria-label="Your Octopus rates"
      className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4"
    >
      <div className="flex items-start gap-3">
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-amber-500/15 text-amber-600 dark:text-amber-300">
          <ChartIcon size={18} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold">Your Octopus rates</p>
          <p className="mt-0.5 text-xs text-[var(--muted)]">
            {tariffTitle(plan.tariff_family, plan.import_display_name)}
            {plan.region ? ` · region ${plan.region}` : ""}
            {plan.current_rate_pence != null
              ? ` · now ${plan.current_rate_pence.toFixed(1)}p/kWh`
              : ""}
          </p>
        </div>
      </div>

      <div className={`mt-4 grid gap-3 ${hasCheapTier ? "sm:grid-cols-2" : "sm:grid-cols-1"}`}>
        {hasCheapTier ? (
          <div
            className={`rounded-xl border p-3 ${
              plan.current_is_cheap
                ? "border-emerald-400/60 bg-emerald-500/10"
                : "border-[var(--border)] bg-[var(--surface-elevated)]"
            }`}
          >
            <p className="text-xs uppercase tracking-wider text-[var(--muted)]">Cheap rate</p>
            <p className="mt-1 text-2xl font-bold tabular-nums text-emerald-600 dark:text-emerald-400">
              {plan.cheap_rate_pence!.toFixed(1)}p
            </p>
            <p className="mt-1 text-sm text-[var(--muted)]">
              {formatWindowRange(plan.cheap_windows)}
            </p>
            {plan.current_is_cheap ? (
              <p className="mt-2 text-xs font-medium text-emerald-700 dark:text-emerald-300">
                Active now
              </p>
            ) : null}
          </div>
        ) : null}

        <div
          className={`rounded-xl border p-3 ${
            !plan.current_is_cheap
              ? "border-amber-400/60 bg-amber-500/10"
              : "border-[var(--border)] bg-[var(--surface-elevated)]"
          }`}
        >
          <p className="text-xs uppercase tracking-wider text-[var(--muted)]">
            {hasCheapTier ? "Peak rate" : "Import rate"}
          </p>
          <p className="mt-1 text-2xl font-bold tabular-nums text-amber-600 dark:text-amber-400">
            {(plan.peak_rate_pence ?? plan.cheap_rate_pence)?.toFixed(1)}p
          </p>
          <p className="mt-1 text-sm text-[var(--muted)]">
            {hasCheapTier ? formatWindowRange(plan.peak_windows) : "All day"}
          </p>
          {!plan.current_is_cheap ? (
            <p className="mt-2 text-xs font-medium text-amber-700 dark:text-amber-300">
              Active now
            </p>
          ) : null}
        </div>
      </div>

      {plan.planned_cheap_windows.length > 0 ? (
        <div className="mt-3 rounded-lg border border-[var(--border)] bg-[var(--surface-elevated)] p-3">
          <p className="text-xs font-semibold uppercase tracking-wider text-[var(--muted)]">
            Planned smart-charge windows
          </p>
          <ul className="mt-2 space-y-1 text-sm">
            {plan.planned_cheap_windows.slice(0, 3).map((window) => (
              <li key={window.start} className="tabular-nums text-[var(--muted)]">
                {formatLocalTime(window.start)}–{formatLocalTime(window.end)}
                {window.source ? ` · ${window.source}` : ""}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}
