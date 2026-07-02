"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { MetricTile } from "@/components/finance/MetricTile";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { cashflowForecastSchema, type CashflowForecast } from "@/lib/finance-schemas";
import { formatGbp } from "@/lib/money";

const horizons = [30, 60, 90] as const;

export default function CashFlowPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [horizon, setHorizon] = useState<number>(30);
  const [forecast, setForecast] = useState<CashflowForecast | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const data = await apiClient.get<unknown>(`/finance/cashflow?horizon=${horizon}`);
      setForecast(cashflowForecastSchema.parse(data));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load cash flow");
    }
  }, [horizon]);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [user, load]);

  if (authLoading || !user) return <AuthLoadingShell />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Cash Flow"
        description="30, 60, and 90-day forecast with expected income, bills, debt payments, and tax."
        actions={
          <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1">
            {horizons.map((h) => (
              <button
                key={h}
                type="button"
                className={`rounded-md px-3 py-1 text-sm ${horizon === h ? "bg-emerald-500 text-white" : ""}`}
                onClick={() => setHorizon(h)}
              >
                {h}d
              </button>
            ))}
          </div>
        }
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      {forecast ? (
        <>
          <div className="mt-6 grid gap-4 sm:grid-cols-3">
            <MetricTile label="Starting balance" value={forecast.starting_balance_gbp} />
            <MetricTile
              label="Projected balance"
              value={forecast.projected_balance_gbp}
              warning={forecast.cash_pressure_warning}
            />
            <MetricTile label="Horizon" value={forecast.horizon_days} format="number" hint="days" />
          </div>
          {forecast.cash_pressure_warning ? (
            <p className="mt-4 rounded-xl border border-amber-400/35 bg-amber-500/10 px-4 py-3 text-sm">
              {forecast.warning_message}
            </p>
          ) : null}
          <ul className="mt-6 space-y-2">
            {forecast.entries.map((e) => (
              <li
                key={e.id}
                className="flex items-center justify-between rounded-xl border border-[var(--border)] px-4 py-3 text-sm"
              >
                <span>
                  {e.label}{" "}
                  <span className="text-[var(--muted)]">
                    · {e.forecast_date} · {e.entry_type}
                  </span>
                </span>
                <span className={`font-semibold tabular-nums ${e.amount_gbp >= 0 ? "text-emerald-600" : ""}`}>
                  {formatGbp(e.amount_gbp)}
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-8 text-sm text-[var(--muted)]">Loading forecast…</p>
      )}
    </AppShell>
  );
}
