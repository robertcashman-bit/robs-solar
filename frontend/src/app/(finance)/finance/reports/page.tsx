"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { MetricTile } from "@/components/finance/MetricTile";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { financeReportsSchema, type FinanceReports } from "@/lib/finance-schemas";
import { formatGbp, formatMonthLabel, currentMonthKey } from "@/lib/money";

export default function ReportsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [reports, setReports] = useState<FinanceReports | null>(null);
  const [error, setError] = useState<string | null>(null);
  const month = currentMonthKey();

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => {
      void (async () => {
        try {
          const data = await apiClient.get<unknown>(`/finance/reports?month=${month}`);
          setReports(financeReportsSchema.parse(data));
        } catch (err) {
          setError(err instanceof Error ? err.message : "Failed to load reports");
        }
      })();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [user, month]);

  if (authLoading || !user) return <AuthLoadingShell />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Reports"
        description={`Monthly finance report for ${formatMonthLabel(month)}.`}
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      {reports ? (
        <div className="mt-6 space-y-8">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <MetricTile label="Net worth" value={reports.net_worth_gbp} />
            <MetricTile label="Total debt" value={reports.total_debt_gbp} warning />
            <MetricTile label="Energy savings" value={reports.energy_savings_gbp} positive />
            <MetricTile label="Debt reduction" value={reports.debt_reduction_gbp} />
          </div>
          <section className="rounded-2xl border border-[var(--border)] p-4">
            <h2 className="font-semibold">Energy savings report</h2>
            <p className="mt-2 text-sm text-[var(--muted)]">
              {reports.energy_savings_vs_forecast} — {formatGbp(reports.energy_savings_gbp)} saved this month.
            </p>
            <Link href="/energy/analytics" className="mt-3 inline-block text-sm underline">
              Open energy analytics
            </Link>
          </section>
        </div>
      ) : (
        <p className="mt-8 text-sm text-[var(--muted)]">Loading reports…</p>
      )}
    </AppShell>
  );
}
