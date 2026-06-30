"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { DashboardView } from "@/components/dashboard/DashboardView";
import { AppShell } from "@/components/shared/AppShell";
import { ErrorBanner, OfflineBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import {
  connectivitySchema,
  healthResponseSchema,
  metricSummarySchema,
  metricCompareSchema,
  octopusTariffSchema,
  evStatusSchema,
  type ConnectivityStatus,
  type MetricCompare,
  type MetricSummary,
  type OctopusTariff,
} from "@/lib/schemas";
import { useLiveMetrics } from "@/lib/use-live-metrics";

export default function DashboardPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { metrics, error: metricsError, connected, refresh: refreshMetrics } = useLiveMetrics({
    enabled: Boolean(user),
  });
  const [connectivity, setConnectivity] = useState<ConnectivityStatus | null>(null);
  const [summary, setSummary] = useState<MetricSummary | null>(null);
  const [compare, setCompare] = useState<MetricCompare | null>(null);
  const [readOnly, setReadOnly] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [offline, setOffline] = useState(false);
  const [polling, setPolling] = useState(true);
  const [agilePricePence, setAgilePricePence] = useState<number | null>(null);
  const [octopusTariff, setOctopusTariff] = useState<OctopusTariff | null>(null);
  const [evCharging, setEvCharging] = useState(false);

  const refreshMeta = useCallback(async () => {
    setError(null);
    setOffline(false);
    try {
      const [healthData, connectivityData, summaryData, compareData] = await Promise.all([
        apiClient.get<unknown>("/health"),
        apiClient.get<unknown>("/metrics/connectivity"),
        apiClient.get<unknown>("/metrics/summary?range=day"),
        apiClient.get<unknown>("/metrics/compare").catch(() => null),
      ]);
      const health = healthResponseSchema.parse(healthData);
      setReadOnly(health.read_only);
      setConnectivity(connectivitySchema.parse(connectivityData));
      setSummary(metricSummarySchema.parse(summaryData));
      if (compareData) {
        try {
          setCompare(metricCompareSchema.parse(compareData));
        } catch {
          setCompare(null);
        }
      } else {
        setCompare(null);
      }
      try {
        const octopus = await apiClient.get<{
          tariff?: unknown;
          agile?: { current?: { value_inc_vat: number } };
          current?: { value_inc_vat: number };
        }>("/octopus/prices");
        if (octopus.tariff) {
          try {
            setOctopusTariff(octopusTariffSchema.parse(octopus.tariff));
          } catch {
            setOctopusTariff(null);
          }
        }
        const agileCurrent = octopus.agile?.current ?? octopus.current;
        setAgilePricePence(agileCurrent?.value_inc_vat ?? null);
      } catch {
        setAgilePricePence(null);
        setOctopusTariff(null);
      }
      try {
        const ev = evStatusSchema.parse(await apiClient.get("/metrics/ev/status"));
        setEvCharging(ev.car_charging_likely);
      } catch {
        setEvCharging(false);
      }
    } catch (fetchError) {
      if (fetchError instanceof ApiError && fetchError.status >= 500) {
        setOffline(true);
      }
      setError(fetchError instanceof Error ? fetchError.message : "Failed to load dashboard");
    }
  }, []);

  const refresh = useCallback(async () => {
    await Promise.all([refreshMetrics(), refreshMeta()]);
  }, [refreshMetrics, refreshMeta]);

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) {
      return;
    }
    let active = true;
    (async () => {
      setLoading(true);
      try {
        await refreshMeta();
        await refreshMetrics();
      } catch {
        /* errors handled in hooks/callbacks */
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    })();
    return () => {
      active = false;
    };
  }, [user, refreshMeta, refreshMetrics]);

  useEffect(() => {
    if (!user || !polling) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshMeta();
    }, 30000);
    return () => window.clearInterval(timer);
  }, [user, polling, refreshMeta]);

  if (authLoading || !user) {
    return null;
  }

  const displayError = error ?? metricsError;

  return (
    <AppShell>
      <div className="space-y-4">
        <PageHeader
          eyebrow="Home"
          title={
            <>
              Savings <span className="text-gradient-solar">control centre</span>
            </>
          }
          description={
            connected
              ? "Live inverter data with savings insights and recommended actions."
              : "Live metrics with polling fallback — insights update as data arrives."
          }
          actions={
            <>
              <button type="button" onClick={() => void refresh()} className="solar-btn-ghost">
                Refresh now
              </button>
              <button
                type="button"
                onClick={() => setPolling((value) => !value)}
                className="solar-btn-ghost"
              >
                {polling ? "Pause summary refresh" : "Resume summary refresh"}
              </button>
            </>
          }
        />

        {offline ? (
          <OfflineBanner message="Backend unavailable or degraded. Showing last known error state." />
        ) : null}
        {displayError ? <ErrorBanner message={displayError} /> : null}

        <DashboardView
          metrics={metrics}
          connectivity={connectivity}
          summary={summary}
          compare={compare}
          loading={loading && !metrics}
          error={null}
          readOnly={readOnly}
          octopusTariff={octopusTariff}
          agilePricePence={agilePricePence}
          evCharging={evCharging}
        />
      </div>
    </AppShell>
  );
}
