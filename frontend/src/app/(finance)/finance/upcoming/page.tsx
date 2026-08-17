"use client";

import { useCallback, useState } from "react";

import { FinanceExportPanel } from "@/components/finance/FinanceExportPanel";
import { HistoryStatsPanel } from "@/components/finance/HistoryStatsPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useRequireAuth } from "@/lib/use-require-auth";
import { formatGbp } from "@/lib/money";
import { useFinanceReload } from "@/lib/use-finance-reload";

type UpcomingItem = {
  date: string;
  label: string;
  amount_gbp: number;
  account: string;
  confidence: string;
  source: string;
};

export default function UpcomingPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const [days, setDays] = useState(30);
  const [items, setItems] = useState<UpcomingItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiClient.get<{ items: UpcomingItem[] }>(
        `/finance/upcoming?days=${days}`,
      );
      setItems(data.items ?? []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load upcoming money");
    }
  }, [days]);

  useFinanceReload(load, Boolean(user) && !gated);

  if (gated) {
    return <AuthLoadingShell redirecting={redirecting} />;
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Upcoming money"
        description="Predicted bills and income from confirmed recurring rules and cashflow entries."
        actions={
          <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
            {[7, 30, 90].map((item) => (
              <button
                key={item}
                type="button"
                className={`rounded-md px-3 py-1 text-sm ${days === item ? "bg-emerald-600 text-white" : ""}`}
                onClick={() => setDays(item)}
              >
                {item}d
              </button>
            ))}
          </div>
        }
      />
      <div className="mt-6 space-y-8">
        {error ? <ErrorBanner message={error} /> : null}
        <ul className="space-y-2">
          {items.length === 0 ? (
            <li className="text-sm text-[var(--muted)]">
              No predicted items in this window. Confirm recurring rules on Budget, or add
              cashflow entries.
            </li>
          ) : (
            items.map((item) => (
              <li
                key={`${item.date}-${item.label}-${item.amount_gbp}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--border)] px-4 py-3 text-sm"
              >
                <span>
                  {item.label}{" "}
                  <span className="text-[var(--muted)]">
                    · {item.date} · {item.account} · {item.confidence} · {item.source}
                  </span>
                </span>
                <span className="font-semibold tabular-nums">{formatGbp(item.amount_gbp)}</span>
              </li>
            ))
          )}
        </ul>
        <HistoryStatsPanel />
        <FinanceExportPanel />
      </div>
    </AppShell>
  );
}
