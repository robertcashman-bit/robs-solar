"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { AccountStatements } from "@/components/finance/AccountStatements";
import { MetricTile } from "@/components/finance/MetricTile";
import { PlHistoryChart, type PlHistoryPoint } from "@/components/finance/PlHistoryChart";
import { QuickFileStatements } from "@/components/finance/QuickFileStatements";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PageLoading } from "@/components/shared/PageLoading";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  financeOverviewSchema,
  financeReportsSchema,
  financeAccountSchema,
  financeLiabilitySchema,
  type FinanceAccount,
  type FinanceLiability,
  type FinanceOverview,
  type FinanceReports,
} from "@/lib/finance-schemas";
import { formatGbp, formatMonthLabel, currentMonthKey } from "@/lib/money";
import { z } from "zod";

export default function ReportsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [reports, setReports] = useState<FinanceReports | null>(null);
  const [overview, setOverview] = useState<FinanceOverview | null>(null);
  const [accounts, setAccounts] = useState<FinanceAccount[]>([]);
  const [liabilities, setLiabilities] = useState<FinanceLiability[]>([]);
  const [plHistory, setPlHistory] = useState<PlHistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const month = currentMonthKey();

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [reportsData, overviewData, accountsData, liabilitiesData, plData] = await Promise.all([
        apiClient.get<unknown>(`/finance/reports?month=${month}`),
        apiClient.get<unknown>("/finance/overview"),
        apiClient.get<unknown>("/finance/accounts"),
        apiClient.get<unknown>("/finance/liabilities"),
        apiClient.get<unknown>("/finance/reports/pl-history?months=12").catch(() => ({ points: [] })),
      ]);
      setReports(financeReportsSchema.parse(reportsData));
      setOverview(financeOverviewSchema.parse(overviewData));
      setAccounts(z.array(financeAccountSchema).parse(accountsData));
      setLiabilities(z.array(financeLiabilitySchema).parse(liabilitiesData));
      setPlHistory(
        z
          .object({
            points: z.array(
              z.object({
                month: z.string(),
                turnover_gbp: z.number(),
                expenses_gbp: z.number(),
                profit_gbp: z.number(),
              }),
            ),
          })
          .parse(plData).points,
      );
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reports");
      setReports(null);
      setOverview(null);
    } finally {
      setLoading(false);
    }
  }, [month]);

  useEffect(() => {
    if (!user) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [user, load, reloadKey]);

  if (authLoading || !user) return <AuthLoadingShell />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Reports"
        description={`Monthly finance report for ${formatMonthLabel(month)}.`}
        actions={
          <button
            type="button"
            className="solar-btn-secondary text-sm"
            onClick={() => setReloadKey((k) => k + 1)}
          >
            Try again
          </button>
        }
      />
      {error ? (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      ) : null}
      {loading ? (
        <div className="mt-6">
          <PageLoading label="Loading reports" rows={3} />
        </div>
      ) : reports && overview ? (
        <div className="mt-6 space-y-10">
          <section className="space-y-4">
            <h2 className="solar-section-title">Business reports</h2>
            <QuickFileStatements reports={reports.quickfile_reports} variant="document" />
          </section>

          <section className="space-y-4">
            <h2 className="solar-section-title">Monthly P&amp;L</h2>
            <div className="rounded-2xl border border-[var(--border)] p-4">
              <PlHistoryChart points={plHistory} />
            </div>
          </section>

          <section className="space-y-4">
            <h2 className="solar-section-title">Accounts &amp; net worth</h2>
            <AccountStatements
              overview={overview}
              accounts={accounts}
              liabilities={liabilities}
            />
          </section>

          <section className="space-y-4">
            <h2 className="solar-section-title">Summary</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <MetricTile label="Net worth" value={reports.net_worth_gbp} amountRole="signed" />
              <MetricTile label="Total debt" value={Math.abs(reports.total_debt_gbp)} amountRole="debt" />
            </div>
          </section>

          <section className="rounded-2xl border border-[var(--border)] bg-[var(--surface)] p-4">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
              Energy savings
            </h2>
            <p className="mt-2 text-sm">
              {reports.energy_savings_vs_forecast} — {formatGbp(reports.energy_savings_gbp)} saved
              this month.
            </p>
            <Link href="/energy/analytics" className="mt-3 inline-block text-sm underline">
              Open energy analytics
            </Link>
          </section>
        </div>
      ) : (
        <div className="mt-6">
          <EmptyState
            title="Reports unavailable"
            description="Could not load the monthly report. Use Try again, or check that the backend is running."
          />
        </div>
      )}
    </AppShell>
  );
}
