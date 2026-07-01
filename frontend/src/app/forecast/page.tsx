"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shared/AppShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
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
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        setForecast(await apiClient.get("/forecast"));
        const strategyData = await apiClient.get(
          `/metrics/forecast-strategy?solar_level=${solarLevel}`,
        );
        setStrategy(forecastStrategySchema.parse(strategyData));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Forecast unavailable");
      }
    })();
  }, [user, solarLevel]);

  if (authLoading || !user) return null;

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Outlook"
          icon={<SunIcon size={22} />}
          title={<span className="text-gradient-solar">Solar forecast &amp; strategy</span>}
          description="Predicted PV generation and tomorrow's battery strategy."
        />
        {error ? <ErrorBanner message={error} /> : null}

        {strategy ? (
          <section className="solar-card">
            <h2 className="solar-section-title">Tomorrow&apos;s strategy</h2>
            <p className="mt-2 text-lg font-semibold">{strategy.headline}</p>
            <p className="mt-1 text-sm text-[var(--muted)]">{strategy.detail}</p>
            <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-[var(--muted)]">Overnight charge target</dt>
                <dd className="font-semibold">{strategy.overnight_charge_target_pct}%</dd>
              </div>
              <div>
                <dt className="text-[var(--muted)]">Daytime reserve</dt>
                <dd className="font-semibold">{strategy.daytime_reserve_pct}%</dd>
              </div>
            </dl>
            {strategy.fill_battery_overnight ? (
              <p className="mt-3 rounded-lg border border-sky-400/30 bg-sky-500/10 px-3 py-2 text-sm">
                Set Sunsynk timer to charge from your off-peak window and enable grid charge.
              </p>
            ) : (
              <p className="mt-3 rounded-lg border border-amber-400/30 bg-amber-500/10 px-3 py-2 text-sm">
                Avoid overcharging overnight — leave room for tomorrow&apos;s solar generation.
              </p>
            )}
          </section>
        ) : null}

        <label className="block text-sm font-medium">
          Expected solar level (override)
          <select
            value={solarLevel}
            onChange={(e) => setSolarLevel(e.target.value)}
            className="solar-input mt-1 max-w-xs"
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </label>

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
            </div>
          ))}
        </section>
      </div>
    </AppShell>
  );
}
