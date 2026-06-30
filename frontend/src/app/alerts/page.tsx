"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shared/AppShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
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

export default function AlertsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        const data = await apiClient.get<{ alerts: Alert[] }>("/alerts");
        setAlerts(data.alerts);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load alerts");
      }
    })();
  }, [user]);

  if (authLoading || !user) return null;

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Monitoring"
          icon={<AlertIcon size={22} />}
          title="Alerts"
          description="SOC, import, pricing, and connectivity notifications."
        />
        {error ? <ErrorBanner message={error} /> : null}
        <section className="space-y-2">
          {alerts.length === 0 ? (
            <p className="solar-card text-[var(--muted)]">No active alerts.</p>
          ) : (
            alerts.map((a) => (
              <article key={a.id} className="solar-card flex flex-wrap items-center justify-between gap-2">
                <div>
                  <p className="text-xs uppercase tracking-wide text-[var(--muted)]">{a.severity}</p>
                  <p className="font-medium">{a.message}</p>
                  <p className="text-xs text-[var(--muted)]">{new Date(a.timestamp).toLocaleString()}</p>
                </div>
                {canWrite(user) && !a.acknowledged ? (
                  <button
                    type="button"
                    className="solar-btn-ghost"
                    onClick={() =>
                      void apiClient.post(`/alerts/${a.id}/acknowledge`, {}).then(() =>
                        setAlerts((prev) =>
                          prev.map((x) => (x.id === a.id ? { ...x, acknowledged: true } : x)),
                        ),
                      )
                    }
                  >
                    Acknowledge
                  </button>
                ) : null}
              </article>
            ))
          )}
        </section>
      </div>
    </AppShell>
  );
}
