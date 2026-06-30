"use client";

import type { DispatchResponse } from "@/lib/schemas";

type DispatchWindowsProps = {
  dispatches: DispatchResponse | null;
  className?: string;
};

function formatWindow(start: string, end: string) {
  const opts: Intl.DateTimeFormatOptions = { hour: "2-digit", minute: "2-digit" };
  return `${new Date(start).toLocaleTimeString([], opts)} – ${new Date(end).toLocaleTimeString([], opts)}`;
}

export function DispatchWindows({ dispatches, className = "" }: DispatchWindowsProps) {
  if (!dispatches) {
    return (
      <p className={`text-sm text-[var(--muted)] ${className}`}>
        Configure Octopus to see IOG cheap-charging windows.
      </p>
    );
  }

  const { off_peak_window, planned, completed } = dispatches;

  return (
    <section className={`space-y-4 ${className}`} aria-label="IOG cheap charging windows">
      <div>
        <h3 className="solar-section-title">Intelligent Octopus Go — cheap windows</h3>
        <p className="mt-1 text-sm text-[var(--muted)]">
          Off-peak import and smart-charge dispatches from your Hypervolt/Tesla setup. Battery
          auto-align uses these windows when enabled.
        </p>
      </div>

      <div className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3">
        <p className="text-xs font-medium uppercase tracking-wide text-emerald-700 dark:text-emerald-300">
          Daily off-peak window
        </p>
        <p className="mt-1 text-lg font-semibold tabular-nums">
          {off_peak_window.start} – {off_peak_window.end}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <h4 className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">
            Upcoming dispatches
          </h4>
          {planned.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--muted)]">
              None scheduled right now — Octopus adds bonus slots when your EV needs charging.
            </p>
          ) : (
            <ul className="mt-2 space-y-1 text-sm">
              {planned.map((window) => (
                <li key={`${window.start}-${window.end}`} className="tabular-nums">
                  {formatWindow(window.start, window.end)}
                  {window.delta_kwh != null ? ` · ~${window.delta_kwh.toFixed(1)} kWh` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div>
          <h4 className="text-sm font-semibold text-[var(--muted)]">Recent dispatches</h4>
          {completed.length === 0 ? (
            <p className="mt-2 text-sm text-[var(--muted)]">No recent history.</p>
          ) : (
            <ul className="mt-2 space-y-1 text-sm text-[var(--muted)]">
              {completed.slice(0, 6).map((window) => (
                <li key={`${window.start}-${window.end}`} className="tabular-nums">
                  {formatWindow(window.start, window.end)}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
