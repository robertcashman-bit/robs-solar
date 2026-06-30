"use client";

import type { MetricCompare } from "@/lib/schemas";

type TodayCompareStripProps = {
  compare: MetricCompare | null;
  loading?: boolean;
};

function formatDelta(today: number, yesterday: number, unit: string, higherIsBetter: boolean) {
  const diff = today - yesterday;
  if (Math.abs(diff) < 0.01) {
    return { text: "No change", tone: "neutral" as const };
  }
  const improved = higherIsBetter ? diff > 0 : diff < 0;
  const sign = diff > 0 ? "+" : "";
  const formatted =
    unit === "GBP" || unit === "£"
      ? `${sign}£${Math.abs(diff).toFixed(2)}`
      : `${sign}${diff.toFixed(1)}${unit === "%" ? "%" : ` ${unit}`}`;
  return {
    text: `${formatted} vs yesterday`,
    tone: improved ? ("up" as const) : ("down" as const),
  };
}

export function TodayCompareStrip({ compare, loading }: TodayCompareStripProps) {
  if (loading) {
    return (
      <section aria-label="Today vs yesterday loading" className="solar-skeleton h-24 rounded-2xl" />
    );
  }

  if (!compare) {
    return null;
  }

  return (
    <section aria-label="Today vs yesterday" className="solar-card">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <h3 className="solar-section-title">Today vs yesterday</h3>
        <p className="text-xs text-[var(--muted)]">Rolling 24h compared to prior 24h</p>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {compare.deltas.map((delta) => {
          const { text, tone } = formatDelta(
            delta.today,
            delta.yesterday,
            delta.unit,
            delta.higher_is_better,
          );
          return (
            <article
              key={delta.label}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3"
            >
              <p className="text-xs font-medium text-[var(--muted)]">{delta.label}</p>
              <p className="mt-1 text-lg font-bold tabular-nums">
                {delta.unit === "GBP"
                  ? `£${delta.today.toFixed(2)}`
                  : `${delta.today.toFixed(1)}${delta.unit === "%" ? "%" : ` ${delta.unit}`}`}
              </p>
              <p
                className={`mt-0.5 text-xs font-medium ${
                  tone === "up"
                    ? "text-emerald-600 dark:text-emerald-400"
                    : tone === "down"
                      ? "text-rose-600 dark:text-rose-400"
                      : "text-[var(--muted)]"
                }`}
              >
                {text}
              </p>
            </article>
          );
        })}
      </div>
    </section>
  );
}
