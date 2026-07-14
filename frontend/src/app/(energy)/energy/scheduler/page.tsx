"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { DispatchTimeline } from "@/components/scheduler/DispatchTimeline";
import { LiveInverterSettings } from "@/components/scheduler/LiveInverterSettings";
import { OctopusPriceTimeline } from "@/components/scheduler/OctopusPriceTimeline";
import { TouTimeline } from "@/components/scheduler/TouTimeline";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { InfoBanner } from "@/components/shared/InfoBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { GaugeIcon } from "@/components/shared/icons";
import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { dispatchResponseSchema, inverterSettingsSchema } from "@/lib/schemas";
import {
  STRATEGY_PRESETS,
  type PriceRate,
  type StrategyPreset,
} from "@/lib/scheduler-presets";

export default function SchedulerPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [activePreset, setActivePreset] = useState<StrategyPreset>(STRATEGY_PRESETS[0]);
  const [octopusRates, setOctopusRates] = useState<PriceRate[]>([]);
  const [dispatches, setDispatches] = useState(
    null as ReturnType<typeof dispatchResponseSchema.parse> | null,
  );
  const [liveSettings, setLiveSettings] = useState(
    null as ReturnType<typeof inverterSettingsSchema.parse> | null,
  );
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) return;
    void (async () => {
      try {
        const data = await apiClient.get<{ rates: PriceRate[] }>("/octopus/prices");
        setOctopusRates(data.rates ?? []);
      } catch {
        setOctopusRates([]);
      }
    })();
    void (async () => {
      try {
        const data = await apiClient.get("/octopus/dispatches");
        setDispatches(dispatchResponseSchema.parse(data));
      } catch {
        setDispatches(null);
      }
    })();
  }, [user]);

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      const data = await apiClient.get("/controls/settings");
      setLiveSettings(inverterSettingsSchema.parse(data));
    } catch (e) {
      setLiveSettings(null);
      if (e instanceof ApiError && e.status === 503) {
        setSettingsError("Live inverter settings are not available in simulator mode.");
      } else {
        setSettingsError(e instanceof Error ? e.message : "Could not load inverter settings");
      }
    } finally {
      setSettingsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    void loadSettings();
  }, [user, loadSettings]);

  if (loading) {
    return <AuthLoadingShell />;
  }

  if (!user) {
    return null;
  }

  return (
    <AppShell>
      <div className="solar-page">
        <PageHeader
          eyebrow="Automation"
          icon={<GaugeIcon size={22} />}
          title="Time-of-use schedule"
          description="See your live Sunsynk bands and preview strategies against Agile prices. This app does not write schedule changes to the inverter."
        />
        {error ? <ErrorBanner message={error} /> : null}

        <InfoBanner>
          Display only — strategy cards below are for comparison. Change the live schedule in Simple
          Solar or Sunsynk Connect.
        </InfoBanner>

        <LiveInverterSettings
          settings={liveSettings}
          loading={settingsLoading}
          error={settingsError}
        />

        <section className="solar-card space-y-4">
          <h3 className="solar-section-title">24-hour timeline</h3>
          <DispatchTimeline dispatches={dispatches} />
          <OctopusPriceTimeline rates={octopusRates} />
          <TouTimeline windows={activePreset.windows} />
          <ul className="space-y-1 text-sm text-[var(--muted)]">
            {activePreset.windows.map((w) => (
              <li key={`${w.start}-${w.action}`}>
                {w.start}–{w.end}: {w.action}
                {w.power_w ? ` @ ${w.power_w} W` : ""}
              </li>
            ))}
          </ul>
        </section>

        <section className="solar-card">
          <h3 className="solar-section-title">Strategy previews</h3>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Select a preset to preview it on the timeline. Nothing is written to the inverter.
          </p>
          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            {STRATEGY_PRESETS.map((preset) => {
              const selected = activePreset.id === preset.id;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => {
                    setError(null);
                    setActivePreset(preset);
                  }}
                  className={`rounded-xl border p-4 text-left transition-all ${
                    selected
                      ? "border-[var(--solar)] bg-amber-500/10 shadow-md"
                      : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)]"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold">{preset.label}</span>
                    <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[0.65rem] font-medium uppercase tracking-wide text-[var(--muted)]">
                      Preview
                    </span>
                  </div>
                  <p className="mt-2 text-sm text-[var(--muted)]">{preset.description}</p>
                  <p className="mt-2 text-xs text-[var(--solar-dark)] dark:text-amber-400">
                    Best for: {preset.bestFor}
                  </p>
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
