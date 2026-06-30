"use client";

import type { PriceRate } from "@/lib/scheduler-presets";
import { priceColorClass } from "@/lib/scheduler-presets";

type OctopusPriceTimelineProps = {
  rates: PriceRate[];
  className?: string;
};

export function OctopusPriceTimeline({ rates, className = "" }: OctopusPriceTimelineProps) {
  const slots = rates.slice(0, 48);

  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-[var(--muted)]">Agile price bands (24h)</p>
        <div className="flex flex-wrap gap-2 text-[0.65rem] text-[var(--muted)]">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-emerald-500" /> Cheap
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-amber-500" /> Mid
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-rose-500" /> Expensive
          </span>
        </div>
      </div>
      <div
        className="flex h-8 items-end gap-px overflow-hidden rounded-lg bg-[var(--surface-sunken)]"
        aria-label="Octopus Agile price timeline"
      >
        {slots.length === 0 ? (
          <p className="w-full px-3 py-2 text-xs text-[var(--muted)]">
            Configure OCTOPUS_API_KEY to overlay live Agile prices.
          </p>
        ) : (
          slots.map((r, i) => (
            <div
              key={`${r.valid_from}-${i}`}
              className={`min-w-[3px] flex-1 rounded-t ${priceColorClass(r.value_inc_vat)}`}
              style={{ height: `${Math.min(100, Math.max(20, r.value_inc_vat * 2.5))}%` }}
              title={`${new Date(r.valid_from).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} — ${r.value_inc_vat.toFixed(1)}p`}
            />
          ))
        )}
      </div>
      <div className="mt-1 flex justify-between text-[0.65rem] text-[var(--muted)]">
        <span>00:00</span>
        <span>12:00</span>
        <span>24:00</span>
      </div>
    </div>
  );
}
