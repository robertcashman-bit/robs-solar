"use client";

import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  compareRangeLabels,
  formatCompareDelta,
  formatMetricValue,
  formatSavings,
  type CompareRange,
} from "@/lib/money";
import { metricCompareSchema, type MetricCompare } from "@/lib/schemas";

const PERIODS: CompareRange[] = ["week", "month"];

type PeriodComparisonPanelProps = {
  loading?: boolean;
};

function CompareBlock({ compare, range }: { compare: MetricCompare; range: CompareRange }) {
  const labels = compareRangeLabels(range);
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h3 className="text-sm font-semibold">{labels.title}</h3>
      <p className="mt-0.5 text-xs text-[var(--muted)]">{labels.subtitle}</p>
      <div className="mt-4 grid gap-3 sm:grid-cols-2">
        {compare.deltas.map((delta) => {
          const { text, tone } = formatCompareDelta(
            delta.today,
            delta.yesterday,
            delta.unit,
            delta.higher_is_better,
            labels.previousLabel,
          );
          const valueText =
            delta.label === "Savings" && (delta.unit === "GBP" || delta.unit === "£")
              ? formatSavings(delta.today, compare.today.currency).headline
              : formatMetricValue(delta.today, delta.unit, compare.today.currency);
          return (
            <div key={delta.label} className="rounded-xl border border-[var(--border)] p-3">
              <p className="text-xs text-[var(--muted)]">{delta.label}</p>
              <p className="mt-1 font-bold tabular-nums">{valueText}</p>
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
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PeriodComparisonPanel({ loading: parentLoading }: PeriodComparisonPanelProps) {
  const [loading, setLoading] = useState(true);
  const [comparisons, setComparisons] = useState<Partial<Record<CompareRange, MetricCompare>>>({});

  useEffect(() => {
    let active = true;
    (async () => {
      setLoading(true);
      try {
        const entries = await Promise.all(
          PERIODS.map(async (range) => {
            const data = await apiClient.get(`/metrics/compare?range=${range}`);
            return [range, metricCompareSchema.parse(data)] as const;
          }),
        );
        if (!active) return;
        setComparisons(Object.fromEntries(entries));
      } catch {
        if (active) setComparisons({});
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  if (parentLoading || loading) {
    return <section className="solar-skeleton h-40 rounded-2xl" aria-label="Period comparison loading" />;
  }

  if (Object.keys(comparisons).length === 0) {
    return null;
  }

  return (
    <section aria-label="Period comparison" className="space-y-4">
      <div>
        <h2 className="solar-section-title">Period comparison</h2>
        <p className="mt-0.5 text-sm text-[var(--muted)]">
          Week and month savings and usage vs the previous period.
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {PERIODS.map((range) =>
          comparisons[range] ? (
            <CompareBlock key={range} compare={comparisons[range]!} range={range} />
          ) : null,
        )}
      </div>
    </section>
  );
}
