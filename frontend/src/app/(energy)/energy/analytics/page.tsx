"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { LiveDataRequiredPanel } from "@/components/dashboard/LiveDataRequiredPanel";
import { PeriodComparisonPanel } from "@/components/analytics/PeriodComparisonPanel";
import { ReconciliationCard } from "@/components/analytics/ReconciliationCard";
import { AnalyticsCharts } from "@/components/analytics/AnalyticsCharts";
import { SavingsHistoryCharts } from "@/components/analytics/SavingsHistoryCharts";
import { SavingsCard } from "@/components/dashboard/SavingsCard";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { ChartIcon } from "@/components/shared/icons";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  historyRangeSchema,
  metricHistorySchema,
  metricSummarySchema,
  type HistoryRange,
  type MetricHistory,
  type MetricSummary,
  reconciliationSchema,
  type Reconciliation,
  savingsHistorySchema,
  type SavingsHistory,
  healthResponseSchema,
} from "@/lib/schemas";

export default function AnalyticsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [range, setRange] = useState<HistoryRange>("day");
  const [history, setHistory] = useState<MetricHistory | null>(null);
  const [summary, setSummary] = useState<MetricSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reconciliation, setReconciliation] = useState<Reconciliation | null>(null);
  const [savingsHistory, setSavingsHistory] = useState<SavingsHistory | null>(null);
  const [dataSource, setDataSource] = useState<"live" | "simulated" | null>(null);
  const [adapterMode, setAdapterMode] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      return;
    }
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const healthData = await apiClient.get<unknown>("/health");
        const health = healthResponseSchema.parse(healthData);
        if (!active) {
          return;
        }
        setDataSource(health.data_source ?? null);
        setAdapterMode(health.adapter_mode);

        if (health.data_source !== "live") {
          setHistory(null);
          setSummary(null);
          setReconciliation(null);
          setSavingsHistory(null);
          return;
        }

        const parsedRange = historyRangeSchema.parse(range);
        const [historyData, summaryData, reconciliationData, savingsData] = await Promise.all([
          apiClient.get(`/metrics/history?range=${parsedRange}`),
          apiClient.get(`/metrics/summary?range=${parsedRange}`),
          apiClient.get(`/metrics/reconciliation?range=${parsedRange}`).catch(() => null),
          apiClient.get(`/metrics/savings-history?range=${parsedRange}`).catch(() => null),
        ]);
        if (!active) {
          return;
        }
        setHistory(metricHistorySchema.parse(historyData));
        setSummary(metricSummarySchema.parse(summaryData));
        if (reconciliationData) {
          setReconciliation(reconciliationSchema.parse(reconciliationData));
        } else {
          setReconciliation(null);
        }
        if (savingsData) {
          setSavingsHistory(savingsHistorySchema.parse(savingsData));
        } else {
          setSavingsHistory(null);
        }
      } catch (fetchError) {
        if (!active) {
          return;
        }
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load analytics");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [user, range]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  if (authLoading) {
    return <AuthLoadingShell />;
  }

  if (!user) {
    return null;
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Insights"
          icon={<ChartIcon size={22} />}
          title={<span className="text-gradient-solar">Analytics</span>}
          description="Historical energy trends, self-consumption, and savings."
        />

        {error ? <ErrorBanner message={error} /> : null}

        {dataSource === "simulated" ? (
          <LiveDataRequiredPanel adapterMode={adapterMode ?? undefined} />
        ) : dataSource === "live" ? (
          <>
            <SavingsCard summary={summary} loading={loading} />
            <PeriodComparisonPanel loading={loading} />
            <ReconciliationCard data={reconciliation} range={range} loading={loading} />
            <SavingsHistoryCharts
              savingsHistory={savingsHistory}
              metricHistory={history}
              currency={summary?.currency}
            />
            <AnalyticsCharts
              history={history}
              summary={summary}
              range={range}
              onRangeChange={setRange}
              loading={loading}
            />
          </>
        ) : (
          <section className="solar-card text-sm text-[var(--muted)]" role="status">
            Checking data source…
          </section>
        )}
      </div>
    </AppShell>
  );
}
