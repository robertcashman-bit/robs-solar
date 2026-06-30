import type { ReactNode } from "react";

export type MetricAccent = "pv" | "battery" | "load" | "import" | "export" | "inverter" | "default";

const accentStyles: Record<
  MetricAccent,
  { bar: string; chip: string; glow: string }
> = {
  pv: {
    bar: "bg-amber-400",
    chip: "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
    glow: "rgba(245, 158, 11, 0.35)",
  },
  battery: {
    bar: "bg-emerald-400",
    chip: "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
    glow: "rgba(16, 185, 129, 0.35)",
  },
  load: {
    bar: "bg-sky-400",
    chip: "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300",
    glow: "rgba(14, 165, 233, 0.35)",
  },
  import: {
    bar: "bg-rose-400",
    chip: "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
    glow: "rgba(244, 63, 94, 0.35)",
  },
  export: {
    bar: "bg-violet-400",
    chip: "bg-violet-100 text-violet-700 dark:bg-violet-900/40 dark:text-violet-300",
    glow: "rgba(139, 92, 246, 0.35)",
  },
  inverter: {
    bar: "bg-indigo-400",
    chip: "bg-indigo-100 text-indigo-700 dark:bg-indigo-900/40 dark:text-indigo-300",
    glow: "rgba(99, 102, 241, 0.35)",
  },
  default: {
    bar: "bg-zinc-400",
    chip: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300",
    glow: "rgba(113, 113, 122, 0.25)",
  },
};

type MetricCardProps = {
  label: string;
  value: string;
  hint?: string;
  icon?: ReactNode;
  accent?: MetricAccent;
  progress?: number;
  animationDelay?: number;
};

export function MetricCard({
  label,
  value,
  hint,
  icon,
  accent = "default",
  progress,
  animationDelay = 0,
}: MetricCardProps) {
  const styles = accentStyles[accent];

  return (
    <article
      className="card-hover animate-fade-in-up group relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface-elevated)] p-5 backdrop-blur-sm"
      style={{ animationDelay: `${animationDelay}ms`, boxShadow: "var(--shadow-sm)" }}
    >
      <div
        className={`absolute inset-x-0 top-0 h-[3px] ${styles.bar} opacity-90 transition-opacity group-hover:opacity-100`}
      />
      <div
        className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
        style={{ background: styles.glow }}
      />

      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="solar-eyebrow">{label}</p>
          <p className="mt-2 text-2xl font-bold tracking-tight tabular-nums">{value}</p>
          {progress !== undefined ? (
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-[var(--surface-sunken)]">
              <div
                className={`h-full rounded-full transition-all duration-700 ease-out ${styles.bar}`}
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
              />
            </div>
          ) : null}
          {hint ? <p className="mt-1.5 text-xs text-[var(--muted)]">{hint}</p> : null}
        </div>
        {icon ? (
          <div
            className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl transition-transform duration-300 group-hover:scale-105 ${styles.chip}`}
          >
            {icon}
          </div>
        ) : null}
      </div>
    </article>
  );
}

export function MetricCardSkeleton() {
  return (
    <div
      className="solar-skeleton relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-5"
      aria-hidden="true"
    >
      <div className="absolute inset-x-0 top-0 h-[3px] bg-[var(--border)]" />
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 space-y-3">
          <div className="h-3 w-20 rounded bg-[var(--border)]" />
          <div className="h-8 w-28 rounded bg-[var(--border)]" />
        </div>
        <div className="h-11 w-11 rounded-xl bg-[var(--border)]" />
      </div>
    </div>
  );
}
