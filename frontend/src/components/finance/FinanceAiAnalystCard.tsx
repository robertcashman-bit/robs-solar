"use client";

import { useState } from "react";

import { apiClient } from "@/lib/api-client";
import { canWrite } from "@/lib/permissions";
import type { UserInfo } from "@/lib/schemas";

const PROMPTS = [
  "Analyse This Month",
  "Explain My Spending",
  "Where Can I Reduce Costs?",
  "Explain My Cashflow Forecast",
  "Compare Last 3 Months",
  "Review Business Costs",
] as const;

type FinanceAiAnalystCardProps = {
  user: UserInfo | null;
};

export function FinanceAiAnalystCard({ user }: FinanceAiAnalystCardProps) {
  const writable = canWrite(user);
  const [busy, setBusy] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  async function run(prompt: string) {
    if (!writable || busy) return;
    setBusy(prompt);
    setNotice(null);
    try {
      const result = await apiClient.post<{
        enabled?: boolean;
        reason?: string;
        message?: string;
        analysis?: string;
        disclaimer?: string;
      }>("/finance/finance-ai/interpret", { prompt });
      if (!result.enabled) {
        setAnalysis(null);
        setNotice(result.reason || result.message || "AI insights are not enabled.");
        return;
      }
      setAnalysis(
        [result.analysis, result.disclaimer].filter(Boolean).join("\n\n"),
      );
    } catch (err) {
      setNotice(err instanceof Error ? err.message : "AI request failed");
    } finally {
      setBusy(null);
    }
  }

  if (!writable) {
    return null;
  }

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
      <h2 className="text-lg font-semibold">AI financial analyst</h2>
      <p className="mt-1 text-sm text-[var(--muted)]">
        Interprets pre-calculated metrics only. Transaction rows are never sent. Core
        budgeting works without AI.
      </p>
      <div className="mt-3 flex flex-wrap gap-2">
        {PROMPTS.map((prompt) => (
          <button
            key={prompt}
            type="button"
            className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium disabled:opacity-50"
            disabled={Boolean(busy)}
            onClick={() => void run(prompt)}
          >
            {busy === prompt ? "Working…" : prompt}
          </button>
        ))}
      </div>
      {notice ? <p className="mt-3 text-sm text-amber-800 dark:text-amber-200">{notice}</p> : null}
      {analysis ? (
        <pre className="mt-3 whitespace-pre-wrap rounded-xl border border-[var(--border)] bg-[var(--background)] p-3 text-sm">
          {analysis}
        </pre>
      ) : null}
    </section>
  );
}
