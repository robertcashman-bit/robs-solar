"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import {
  financeAiAssessmentSchema,
  financeAiStatusSchema,
  type FinanceAiAssessment,
  type FinanceAiStatus,
} from "@/lib/finance-schemas";

type FinanceAiAdviceCardProps = {
  canUse: boolean;
};

export function FinanceAiAdviceCard({ canUse }: FinanceAiAdviceCardProps) {
  const [status, setStatus] = useState<FinanceAiStatus | null>(null);
  const [assessment, setAssessment] = useState<FinanceAiAssessment | null>(null);
  const [assessing, setAssessing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!canUse) return;
    void (async () => {
      try {
        setStatus(financeAiStatusSchema.parse(await apiClient.get("/finance/ai/status")));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load finance AI status");
      }
    })();
  }, [canUse]);

  if (!canUse) return null;

  const runAssessment = async () => {
    setError(null);
    setAssessing(true);
    try {
      setAssessment(financeAiAssessmentSchema.parse(await apiClient.post("/finance/ai/assess")));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Assessment failed");
    } finally {
      setAssessing(false);
    }
  };

  if (status && !status.enabled) {
    return (
      <section
        aria-label="Finance AI advice"
        className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4"
      >
        <h2 className="font-semibold">Finance AI advisor</h2>
        <p className="mt-2 text-sm text-[var(--muted)]">{status.reason}</p>
      </section>
    );
  }

  return (
    <section
      aria-label="Finance AI advice"
      className="rounded-2xl border border-violet-400/30 bg-violet-500/5 p-4"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-semibold">Finance AI advisor</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Read-only insights on personal vs business cash, debts, and QuickFile data.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            className="solar-btn-secondary text-sm"
            disabled={assessing}
            onClick={() => void runAssessment()}
          >
            {assessing ? "Analysing…" : "Assess now"}
          </button>
          <Link href="/finance/assistant" className="solar-btn-ghost text-sm">
            Open chat
          </Link>
        </div>
      </div>
      {error ? <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p> : null}
      {assessment ? (
        <div className="mt-4 space-y-3 text-sm">
          <p>{assessment.summary}</p>
          {assessment.findings.slice(0, 3).map((f) => (
            <div key={f.title} className="rounded-lg border border-[var(--border)] px-3 py-2">
              <p className="font-medium">{f.title}</p>
              <p className="mt-1 text-[var(--muted)]">{f.detail}</p>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
