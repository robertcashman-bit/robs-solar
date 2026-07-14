"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { EmptyState } from "@/components/shared/EmptyState";
import { PageHeader } from "@/components/shared/PageHeader";
import { PageLoading } from "@/components/shared/PageLoading";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { AlertIcon } from "@/components/shared/icons";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";

type Alert = {
  id: number;
  timestamp: string;
  severity: string;
  category: string;
  message: string;
  acknowledged: boolean;
};

function severityTone(severity: string): "positive" | "negative" | "warning" | "neutral" {
  const normalized = severity.toLowerCase();
  if (normalized === "critical" || normalized === "error") return "negative";
  if (normalized === "warning") return "warning";
  if (normalized === "info") return "neutral";
  return "neutral";
}

export default function AlertsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadAlerts = useCallback(async (options?: { silent?: boolean }) => {
    if (!options?.silent) {
      setLoading(true);
    }
    setError(null);
    try {
      const data = await apiClient.get<{ alerts: Alert[] }>("/alerts");
      setAlerts(data.alerts);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load alerts");
    } finally {
      setLoading(false);
      setHasLoaded(true);
    }
  }, []);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    void loadAlerts();
  }, [user, loadAlerts]);

  if (authLoading) {
    return <AuthLoadingShell />;
  }

  if (!user) {
    return null;
  }

  return (
    <AppShell>
      <div className="solar-page">
        <PageHeader
          eyebrow="Monitoring"
          icon={<AlertIcon size={22} />}
          title="Alerts"
          description="Battery, import, pricing, and connectivity notifications from your energy system."
          actions={
            <button
              type="button"
              className="solar-btn-ghost"
              onClick={() => void loadAlerts({ silent: hasLoaded })}
            >
              Refresh
            </button>
          }
        />

        {error ? (
          <div className="space-y-2">
            <ErrorBanner message={error} />
            <button type="button" className="solar-btn-secondary text-sm" onClick={() => void loadAlerts()}>
              Try again
            </button>
          </div>
        ) : null}

        {loading && !hasLoaded ? (
          <PageLoading label="Loading alerts" rows={2} />
        ) : alerts.length === 0 && !error ? (
          <EmptyState
            icon={<AlertIcon size={22} />}
            title="No active alerts"
            description="When your system detects unusual battery levels, high import, or connectivity issues, they will appear here."
          />
        ) : (
          <section className="space-y-3" aria-label="Alert list">
            {alerts.map((alert) => (
              <article
                key={alert.id}
                className={`solar-card flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between ${
                  alert.acknowledged ? "opacity-70" : ""
                }`}
              >
                <div className="min-w-0 space-y-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <StatusBadge label={alert.severity} tone={severityTone(alert.severity)} />
                    <span className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
                      {alert.category}
                    </span>
                    {alert.acknowledged ? (
                      <StatusBadge label="Acknowledged" tone="positive" showDot={false} />
                    ) : null}
                  </div>
                  <p className="font-medium leading-snug">{alert.message}</p>
                  <time
                    className="block text-xs text-[var(--muted)]"
                    dateTime={alert.timestamp}
                  >
                    {new Date(alert.timestamp).toLocaleString()}
                  </time>
                </div>
                {canWrite(user) && !alert.acknowledged ? (
                  <button
                    type="button"
                    className="solar-btn-ghost shrink-0 self-start sm:self-center"
                    onClick={() =>
                      void apiClient.post(`/alerts/${alert.id}/acknowledge`, {}).then(() =>
                        setAlerts((prev) =>
                          prev.map((x) => (x.id === alert.id ? { ...x, acknowledged: true } : x)),
                        ),
                      )
                    }
                  >
                    Acknowledge
                  </button>
                ) : null}
              </article>
            ))}
          </section>
        )}
      </div>
    </AppShell>
  );
}
