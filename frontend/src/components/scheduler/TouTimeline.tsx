"use client";

import type { ScheduleWindow } from "@/lib/scheduler-presets";
import { slotPercent } from "@/lib/scheduler-presets";

type TouTimelineProps = {
  windows: ScheduleWindow[];
};

export function TouTimeline({ windows }: TouTimelineProps) {
  return (
    <div className="relative mt-4 h-20 rounded-xl bg-[var(--surface-sunken)]" aria-label="TOU timeline">
      {windows.map((w) => {
        const startPct = slotPercent(w.start);
        const endPct = slotPercent(w.end);
        const width = endPct >= startPct ? endPct - startPct : 100 - startPct + endPct;
        const color =
          w.action === "charge"
            ? "bg-emerald-500/75 border-emerald-400/50"
            : w.action === "discharge"
              ? "bg-amber-500/75 border-amber-400/50"
              : "bg-slate-400/40 border-slate-400/30";
        return (
          <div
            key={`${w.start}-${w.end}-${w.action}`}
            className={`absolute top-3 h-14 rounded-md border ${color}`}
            style={{ left: `${startPct}%`, width: `${Math.max(width, 2)}%` }}
            title={`${w.start}–${w.end} ${w.action}${w.power_w ? ` @ ${w.power_w}W` : ""}`}
          />
        );
      })}
      <div className="pointer-events-none absolute inset-x-0 bottom-1 flex justify-between px-1 text-[0.6rem] text-[var(--muted)]">
        <span>00</span>
        <span>06</span>
        <span>12</span>
        <span>18</span>
        <span>24</span>
      </div>
    </div>
  );
}
