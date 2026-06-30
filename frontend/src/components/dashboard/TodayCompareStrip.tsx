"use client";

import type { MetricCompare } from "@/lib/schemas";
import {
  compareRangeLabels,
  formatCompareDelta,
  formatMetricValue,
  formatSavings,
  type CompareRange,
} from "@/lib/money";

type TodayCompareStripProps = {
  compare: MetricCompare | null;
  loading?: boolean;
  range: CompareRange;
  onRangeChange: (range: CompareRange) => void;
};

const RANGE_OPTIONS: CompareRange[] = ["day", "week", "month"];

function formatDeltaValue(label: string, value: number, unit: string, currency: string) {
  if (label === "Savings" && (unit === "GBP" || unit === "£")) {
    return formatSavings(value, currency).headline;
  }
  return formatMetricValue(value, unit, currency);
}

export function TodayCompareStrip({
  compare,
  loading,
  range,
  onRangeChange,
}: TodayCompareStripProps) {
  const labels = compareRangeLabels(range);

  if (loading) {
    return (
      <section aria-label="Period comparison loading" className="solar-skeleton h-24 rounded-2xl" />
    );
  }

  if (!compare) {
    return null;
  }

  return (
    <section aria-label={labels.title} className="solar-card">
      <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h3 className="solar-section-title">{labels.title}</h3>
          <p className="text-xs text-[var(--muted)]">{labels.subtitle}</p>
        </div>
        <div
          className="inline-flex rounded-xl border border-[var(--border)] bg-[var(--surface)] p-0.5"
          role="group"
          aria-label="Comparison period"
        >
          {RANGE_OPTIONS.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => onRangeChange(option)}
              className={`rounded-lg px-3 py-1.5 text-xs font-semibold capitalize transition ${
                range === option
                  ? "bg-[var(--foreground)] text-[var(--background)]"
                  : "text-[var(--muted)] hover:text-[var(--foreground)]"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {compare.deltas.map((delta) => {
          const { text, tone } = formatCompareDelta(
            delta.today,
            delta.yesterday,
            delta.unit,
            delta.higher_is_better,
            labels.previousLabel,
          );
          const currency = compare.today.currency;
          return (
            <article
              key={delta.label}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-3"
            >
              <p className="text-xs font-medium text-[var(--muted)]">{delta.label}</p>
              <p className="mt-1 text-lg font-bold tabular-nums">
                {formatDeltaValue(delta.label, delta.today, delta.unit, currency)}
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
