"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ReconciliationCard } from "@/components/analytics/ReconciliationCard";
import { AnalyticsCharts } from "@/components/analytics/AnalyticsCharts";
import { SavingsCard } from "@/components/dashboard/SavingsCard";
import { AppShell } from "@/components/shared/AppShell";
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

  useEffect(() => {
    if (!user) {
      return;
    }
    let active = true;
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const parsedRange = historyRangeSchema.parse(range);
        const [historyData, summaryData, reconciliationData] = await Promise.all([
          apiClient.get(`/metrics/history?range=${parsedRange}`),
          apiClient.get(`/metrics/summary?range=${parsedRange}`),
          apiClient.get(`/metrics/reconciliation?range=${parsedRange}`).catch(() => null),
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

  if (authLoading || !user) {
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

        <SavingsCard summary={summary} loading={loading} />
        <ReconciliationCard data={reconciliation} range={range} loading={loading} />
        <AnalyticsCharts
          history={history}
          summary={summary}
          range={range}
          onRangeChange={setRange}
          loading={loading}
        />
      </div>
    </AppShell>
  );
}
