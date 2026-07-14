"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { EmptyState } from "@/components/shared/EmptyState";
import { InfoBanner } from "@/components/shared/InfoBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { PageLoading } from "@/components/shared/PageLoading";
import { SunIcon } from "@/components/shared/icons";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { forecastStrategySchema, type ForecastStrategy } from "@/lib/schemas";

export default function ForecastPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const [forecast, setForecast] = useState<{
    days: { date: string; predicted_kwh: number }[];
    hint?: string | null;
  } | null>(null);
  const [strategy, setStrategy] = useState<ForecastStrategy | null>(null);
  const [solarLevel, setSolarLevel] = useState("medium");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    void (async () => {
      setLoading(true);
      setError(null);
      try {
        const [forecastData, strategyData] = await Promise.all([
          apiClient.get<{ days: { date: string; predicted_kwh: number }[]; hint?: string | null }>(
            "/forecast",
          ),
          apiClient.get(`/metrics/forecast-strategy?solar_level=${solarLevel}`),
        ]);
        if (!active) return;
        setForecast(forecastData);
        setStrategy(forecastStrategySchema.parse(strategyData));
      } catch (e) {
        if (!active) return;
        setError(e instanceof Error ? e.message : "Forecast unavailable");
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [user, solarLevel]);

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
          eyebrow="Outlook"
          icon={<SunIcon size={22} />}
          title={<span className="text-gradient-solar">Solar forecast &amp; strategy</span>}
          description="Predicted PV generation and tomorrow's battery strategy."
        />

        {error ? <ErrorBanner message={error} /> : null}

        <section className="solar-card">
          <label className="block text-sm font-medium" htmlFor="solar-level">
            Expected solar level
            <select
              id="solar-level"
              value={solarLevel}
              onChange={(e) => setSolarLevel(e.target.value)}
              className="solar-input mt-1 max-w-xs"
            >
              <option value="low">Low — overcast</option>
              <option value="medium">Medium — mixed</option>
              <option value="high">High — clear skies</option>
            </select>
          </label>
          <p className="mt-2 text-xs text-[var(--muted)]">
            Override the automatic forecast to see how strategy changes with different weather.
          </p>
        </section>

        {loading ? (
          <PageLoading label="Loading forecast" rows={2} />
        ) : (
          <>
            {strategy ? (
              <section className="solar-card">
                <h2 className="solar-section-title">Tomorrow&apos;s strategy</h2>
                <p className="mt-2 text-lg font-semibold">{strategy.headline}</p>
                <p className="mt-1 text-sm text-[var(--muted)]">{strategy.detail}</p>
                <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
                    <dt className="text-[var(--muted)]">Overnight charge target</dt>
                    <dd className="mt-1 text-xl font-semibold tabular-nums">
                      {strategy.overnight_charge_target_pct}%
                    </dd>
                  </div>
                  <div className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-3">
                    <dt className="text-[var(--muted)]">Daytime reserve</dt>
                    <dd className="mt-1 text-xl font-semibold tabular-nums">
                      {strategy.daytime_reserve_pct}%
                    </dd>
                  </div>
                </dl>
                {strategy.fill_battery_overnight ? (
                  <div className="mt-4">
                    <InfoBanner variant="info">
                      Set Sunsynk timer to charge from your off-peak window and enable grid charge.
                    </InfoBanner>
                  </div>
                ) : (
                  <div className="mt-4">
                    <InfoBanner variant="warning">
                      Avoid overcharging overnight — leave room for tomorrow&apos;s solar generation.
                    </InfoBanner>
                  </div>
                )}
              </section>
            ) : null}

            {forecast?.hint ? <InfoBanner variant="success">{forecast.hint}</InfoBanner> : null}

            {forecast?.days?.length ? (
              <section className="solar-card" aria-label="Generation forecast">
                <h3 className="solar-section-title">Predicted generation</h3>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  {forecast.days.map((day) => (
                    <div key={day.date} className="solar-panel p-4 text-center">
                      <p className="solar-eyebrow">{day.date}</p>
                      <p className="mt-2 text-2xl font-bold tabular-nums">{day.predicted_kwh} kWh</p>
                    </div>
                  ))}
                </div>
              </section>
            ) : !error ? (
              <EmptyState
                icon={<SunIcon size={22} />}
                title="No forecast data"
                description="Forecast data is not available right now. Check your backend connection and try again."
              />
            ) : null}
          </>
        )}
      </div>
    </AppShell>
  );
}
