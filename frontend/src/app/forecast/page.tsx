"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shared/AppShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { SunIcon } from "@/components/shared/icons";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";

export default function ForecastPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [forecast, setForecast] = useState<{
    days: { date: string; predicted_kwh: number }[];
    hint?: string | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        setForecast(await apiClient.get("/forecast"));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Forecast unavailable");
      }
    })();
  }, [user]);

  if (authLoading || !user) return null;

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Outlook"
          icon={<SunIcon size={22} />}
          title={<span className="text-gradient-solar">Solar forecast</span>}
          description="Predicted PV generation for the next 3 days (Open-Meteo)."
        />
        {error ? <ErrorBanner message={error} /> : null}
        {forecast?.hint ? (
          <p className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-sm">
            {forecast.hint}
          </p>
        ) : null}
        <section className="solar-card grid gap-3 sm:grid-cols-3">
          {forecast?.days.map((d) => (
            <div key={d.date} className="solar-panel p-4 text-center">
              <p className="solar-eyebrow">{d.date}</p>
              <p className="mt-2 text-2xl font-bold tabular-nums">{d.predicted_kwh} kWh</p>
              <div
                className="mx-auto mt-3 h-2 max-w-[120px] rounded-full bg-[var(--surface-sunken)]"
                aria-hidden
              >
                <div
                  className="h-2 rounded-full bg-gradient-to-r from-amber-400 to-orange-500"
                  style={{
                    width: `${Math.min(100, (d.predicted_kwh / 25) * 100)}%`,
                  }}
                />
              </div>
            </div>
          ))}
        </section>
      </div>
    </AppShell>
  );
}
