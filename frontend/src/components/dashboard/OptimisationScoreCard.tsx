"use client";

import type { OptimisationScore, OptimisationRecommendation } from "@/lib/schemas";
import { formatCurrencyAmount } from "@/lib/money";

type OptimisationScoreCardProps = {
  score: OptimisationScore | null | undefined;
  topRecommendation?: OptimisationRecommendation | null;
  currency?: string;
};

export function OptimisationScoreCard({
  score,
  topRecommendation,
  currency = "GBP",
}: OptimisationScoreCardProps) {
  if (!score) {
    return (
      <section className="solar-card">
        <h2 className="solar-section-title">Optimisation</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">Score will appear once today&apos;s data is available.</p>
      </section>
    );
  }

  const missed = score.missed_saving_gbp ?? 0;

  return (
    <section className="solar-card">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="solar-section-title">Optimisation score</h2>
          <p className="mt-1 text-4xl font-bold tabular-nums">{score.total}/100</p>
          {missed > 0 ? (
            <p className="mt-1 text-sm text-amber-700 dark:text-amber-300">
              Missed saving estimate: {formatCurrencyAmount(missed, currency)}
            </p>
          ) : null}
        </div>
        {topRecommendation ? (
          <div className="max-w-sm rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)] p-3 text-sm">
            <p className="text-[0.65rem] font-semibold uppercase tracking-wider text-[var(--muted)]">
              Top recommendation
            </p>
            <p className="mt-1 font-semibold">{topRecommendation.title}</p>
            <p className="mt-0.5 text-[var(--muted)]">{topRecommendation.reason}</p>
          </div>
        ) : null}
      </div>
      {score.lost_points_reasons && score.lost_points_reasons.length > 0 ? (
        <ul className="mt-3 space-y-1 text-xs text-[var(--muted)]">
          {score.lost_points_reasons.slice(0, 3).map((reason) => (
            <li key={reason}>• {reason}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
