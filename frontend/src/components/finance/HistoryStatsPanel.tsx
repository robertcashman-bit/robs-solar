"use client";

import { useCallback, useState } from "react";

import { ErrorBanner } from "@/components/shared/Banners";
import { apiClient } from "@/lib/api-client";
import { formatGbp } from "@/lib/money";
import { useFinanceReload } from "@/lib/use-finance-reload";

type HistoryRow = {
  category: string;
  scope: string;
  last_month_gbp: number;
  avg_3m_gbp: number | null;
  avg_6m_gbp: number | null;
  avg_12m_gbp: number | null;
  median_gbp: number | null;
  trend_pct: number;
  volatility: string;
  recommended_budget_gbp: number;
  explain?: Record<string, unknown>;
};

type ExplainPayload = {
  category?: string;
  explain?: Record<string, unknown>;
  recommended_budget_gbp?: number;
  median_gbp?: number | null;
  volatility?: string;
};

export function HistoryStatsPanel() {
  const [scope, setScope] = useState<"personal" | "business">("personal");
  const [rows, setRows] = useState<HistoryRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [explain, setExplain] = useState<ExplainPayload | null>(null);
  const [busyCategory, setBusyCategory] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiClient.get<HistoryRow[]>(
        `/finance/history-stats?scope=${scope}`,
      );
      setRows(data);
      setError(null);
      setExplain(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load history stats");
    }
  }, [scope]);

  useFinanceReload(load, true);

  async function showWhy(category: string) {
    setBusyCategory(category);
    try {
      const data = await apiClient.get<ExplainPayload>(
        `/finance/history-stats/explain?scope=${scope}&category=${encodeURIComponent(category)}`,
      );
      setExplain(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not explain category");
    } finally {
      setBusyCategory(null);
    }
  }

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="solar-section-title">Historical category analysis</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Medians, trends and recommended budgets from stored transactions. Click Why for
            the calculation behind a figure.
          </p>
        </div>
        <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
          {(["personal", "business"] as const).map((item) => (
            <button
              key={item}
              type="button"
              className={`rounded-md px-3 py-1 text-sm capitalize ${
                scope === item ? "bg-emerald-600 text-white" : ""
              }`}
              onClick={() => setScope(item)}
            >
              {item}
            </button>
          ))}
        </div>
      </div>
      {error ? <ErrorBanner message={error} /> : null}
      {rows.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">No transaction history available</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-[var(--border)]">
          <table className="min-w-full text-left text-sm">
            <thead className="border-b border-[var(--border)] text-[var(--muted)]">
              <tr>
                <th className="px-3 py-2">Category</th>
                <th className="px-3 py-2">Last mo</th>
                <th className="px-3 py-2">3m avg</th>
                <th className="px-3 py-2">6m avg</th>
                <th className="px-3 py-2">12m avg</th>
                <th className="px-3 py-2">Median</th>
                <th className="px-3 py-2">Recommended</th>
                <th className="px-3 py-2">Type</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.category} className="border-b border-[var(--border)]/50">
                  <td className="px-3 py-2">{row.category}</td>
                  <td className="px-3 py-2 tabular-nums">{formatGbp(row.last_month_gbp)}</td>
                  <td className="px-3 py-2 tabular-nums">
                    {row.avg_3m_gbp == null ? "—" : formatGbp(row.avg_3m_gbp)}
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {row.avg_6m_gbp == null ? "—" : formatGbp(row.avg_6m_gbp)}
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {row.avg_12m_gbp == null ? "—" : formatGbp(row.avg_12m_gbp)}
                  </td>
                  <td className="px-3 py-2 tabular-nums">
                    {row.median_gbp == null ? "—" : formatGbp(row.median_gbp)}
                  </td>
                  <td className="px-3 py-2 font-medium tabular-nums">
                    {formatGbp(row.recommended_budget_gbp)}
                  </td>
                  <td className="px-3 py-2 text-xs uppercase text-[var(--muted)]">
                    {row.volatility}
                    {row.trend_pct ? ` · ${row.trend_pct > 0 ? "+" : ""}${row.trend_pct}%` : ""}
                  </td>
                  <td className="px-3 py-2">
                    <button
                      type="button"
                      className="text-xs underline"
                      disabled={busyCategory === row.category}
                      onClick={() => void showWhy(row.category)}
                    >
                      {busyCategory === row.category ? "…" : "Why"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {explain ? (
        <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4 text-sm">
          <h3 className="font-semibold">Why: {explain.category}</h3>
          <pre className="mt-2 whitespace-pre-wrap text-xs text-[var(--muted)]">
            {JSON.stringify(explain.explain ?? explain, null, 2)}
          </pre>
        </div>
      ) : null}
    </section>
  );
}
