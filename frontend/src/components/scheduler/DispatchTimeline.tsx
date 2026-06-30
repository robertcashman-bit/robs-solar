"use client";

import type { DispatchResponse } from "@/lib/schemas";

type DispatchTimelineProps = {
  dispatches: DispatchResponse | null;
  className?: string;
};

function minuteOfDay(iso: string): number {
  const date = new Date(iso);
  return date.getHours() * 60 + date.getMinutes();
}

function offPeakSegments(start: string, end: string): Array<{ from: number; to: number }> {
  const [sh, sm] = start.split(":").map(Number);
  const [eh, em] = end.split(":").map(Number);
  const from = sh * 60 + sm;
  const to = eh * 60 + em;
  if (from < to) return [{ from, to }];
  return [
    { from, to: 24 * 60 },
    { from: 0, to },
  ];
}

export function DispatchTimeline({ dispatches, className = "" }: DispatchTimelineProps) {
  const segments: Array<{ from: number; to: number; kind: "offpeak" | "dispatch" }> = [];

  if (dispatches) {
    for (const seg of offPeakSegments(
      dispatches.off_peak_window.start,
      dispatches.off_peak_window.end,
    )) {
      segments.push({ ...seg, kind: "offpeak" });
    }
    for (const window of dispatches.planned) {
      segments.push({
        from: minuteOfDay(window.start),
        to: minuteOfDay(window.end),
        kind: "dispatch",
      });
    }
  }

  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-[var(--muted)]">IOG cheap windows (24h)</p>
        <div className="flex flex-wrap gap-2 text-[0.65rem] text-[var(--muted)]">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-emerald-500" /> Off-peak
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-sm bg-sky-500" /> Smart dispatch
          </span>
        </div>
      </div>
      <div
        className="relative h-8 overflow-hidden rounded-lg bg-[var(--surface-sunken)]"
        aria-label="IOG cheap window timeline"
      >
        {segments.length === 0 ? (
          <p className="px-3 py-2 text-xs text-[var(--muted)]">No IOG window data.</p>
        ) : (
          segments.map((segment, index) => {
            const left = (segment.from / (24 * 60)) * 100;
            const width = Math.max(0.5, ((segment.to - segment.from) / (24 * 60)) * 100);
            return (
              <div
                key={`${segment.kind}-${segment.from}-${index}`}
                className={`absolute top-1 bottom-1 rounded ${
                  segment.kind === "offpeak" ? "bg-emerald-500/80" : "bg-sky-500/80"
                }`}
                style={{ left: `${left}%`, width: `${width}%` }}
              />
            );
          })
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
