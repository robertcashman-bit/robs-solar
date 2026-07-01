"use client";

import { useState } from "react";

import { apiClient } from "@/lib/api-client";
import type { OptimisationRecommendation } from "@/lib/schemas";
import { formatCurrencyAmount } from "@/lib/money";

type RecommendationsPanelProps = {
  recommendations: OptimisationRecommendation[];
  currency?: string;
  canApply?: boolean;
  onChanged?: () => void;
};

export function RecommendationsPanel({
  recommendations,
  currency = "GBP",
  canApply = false,
  onChanged,
}: RecommendationsPanelProps) {
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (recommendations.length === 0) {
    return (
      <section className="solar-card">
        <h2 className="solar-section-title">Recommendations</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">No optimisation changes suggested right now.</p>
      </section>
    );
  }

  const handleApply = async (id: number) => {
    setBusyId(id);
    setError(null);
    try {
      const result = (await apiClient.post(`/recommendations/${id}/apply`)) as {
        success: boolean;
        message: string;
        manual_instructions?: string;
      };
      if (!result.success && result.manual_instructions) {
        setError(result.manual_instructions);
      }
      onChanged?.();
    } catch (applyError) {
      setError(applyError instanceof Error ? applyError.message : "Apply failed");
    } finally {
      setBusyId(null);
    }
  };

  const handleDismiss = async (id: number) => {
    setBusyId(id);
    setError(null);
    try {
      await apiClient.post(`/recommendations/${id}/dismiss`);
      onChanged?.();
    } catch (dismissError) {
      setError(dismissError instanceof Error ? dismissError.message : "Dismiss failed");
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="solar-card">
      <h2 className="solar-section-title">Recommendations</h2>
      <ul className="mt-3 space-y-3">
        {recommendations.map((rec) => (
          <li
            key={rec.id}
            className="rounded-xl border border-[var(--border)] bg-[var(--surface-sunken)] p-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div>
                <p className="font-semibold">{rec.title}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">{rec.reason}</p>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  {rec.current_setting} → {rec.proposed_setting} · Risk: {rec.risk_level}
                </p>
                {rec.estimated_extra_saving_gbp > 0 ? (
                  <p className="mt-1 text-sm font-medium text-emerald-700 dark:text-emerald-300">
                    Est. extra saving: {formatCurrencyAmount(rec.estimated_extra_saving_gbp, currency)}
                  </p>
                ) : null}
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="solar-btn-secondary text-xs"
                  onClick={() => setExpandedId(expandedId === rec.id ? null : rec.id)}
                >
                  View calculation
                </button>
                {canApply && rec.status === "pending" ? (
                  <>
                    {rec.can_auto_apply ? (
                      <button
                        type="button"
                        disabled={busyId === rec.id}
                        className="solar-btn-primary text-xs"
                        onClick={() => void handleApply(rec.id)}
                      >
                        Apply
                      </button>
                    ) : null}
                    <button
                      type="button"
                      disabled={busyId === rec.id}
                      className="solar-btn-secondary text-xs"
                      onClick={() => void handleDismiss(rec.id)}
                    >
                      Dismiss
                    </button>
                  </>
                ) : null}
              </div>
            </div>
            {expandedId === rec.id ? (
              <div className="mt-3 rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3 text-xs text-[var(--muted)]">
                <p>{rec.calculation_detail || "No calculation detail."}</p>
                {rec.manual_instructions ? (
                  <p className="mt-2 font-medium text-[var(--foreground)]">{rec.manual_instructions}</p>
                ) : null}
              </div>
            ) : null}
          </li>
        ))}
      </ul>
      {error ? <p className="mt-2 text-sm text-amber-700 dark:text-amber-300">{error}</p> : null}
    </section>
  );
}
