"use client";

import type { SystemWarning } from "@/lib/schemas";

const severityStyles: Record<SystemWarning["severity"], string> = {
  green: "border-emerald-400/40 bg-emerald-500/10 text-emerald-900 dark:text-emerald-100",
  amber: "border-amber-400/40 bg-amber-500/10 text-amber-900 dark:text-amber-200",
  red: "border-red-400/40 bg-red-500/10 text-red-900 dark:text-red-100",
};

type WarningsPanelProps = {
  warnings: SystemWarning[];
  statusHeadline?: string;
};

export function WarningsPanel({ warnings, statusHeadline }: WarningsPanelProps) {
  return (
    <section className="solar-card">
      <h2 className="solar-section-title">System status</h2>
      {statusHeadline ? (
        <p className="mt-2 text-sm font-medium text-[var(--foreground)]">{statusHeadline}</p>
      ) : null}
      {warnings.length === 0 ? (
        <p className="mt-2 text-sm text-emerald-700 dark:text-emerald-300">No active warnings.</p>
      ) : (
        <ul className="mt-3 space-y-2">
          {warnings.map((w) => (
            <li
              key={w.id}
              className={`rounded-lg border px-3 py-2 text-sm ${severityStyles[w.severity]}`}
            >
              <p className="font-semibold">{w.title}</p>
              <p className="mt-0.5 opacity-90">{w.message}</p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
