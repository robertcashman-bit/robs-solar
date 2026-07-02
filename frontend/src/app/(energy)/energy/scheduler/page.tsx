"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AutoAlignPanel } from "@/components/scheduler/AutoAlignPanel";
import { DispatchTimeline } from "@/components/scheduler/DispatchTimeline";
import { EditableTouBands } from "@/components/scheduler/EditableTouBands";
import { LiveInverterSettings } from "@/components/scheduler/LiveInverterSettings";
import { OctopusPriceTimeline } from "@/components/scheduler/OctopusPriceTimeline";
import { TouTimeline } from "@/components/scheduler/TouTimeline";
import { InstallerAccessPanel } from "@/components/settings/InstallerAccessPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { ConfirmDialog } from "@/components/shared/ConfirmDialog";
import { PageHeader } from "@/components/shared/PageHeader";
import { GaugeIcon } from "@/components/shared/icons";
import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";
import { controlWriteResultSchema, dispatchResponseSchema, inverterSettingsSchema } from "@/lib/schemas";
import {
  STRATEGY_PRESETS,
  type PriceRate,
  type StrategyPreset,
} from "@/lib/scheduler-presets";

export default function SchedulerPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [activePreset, setActivePreset] = useState<StrategyPreset>(STRATEGY_PRESETS[0]);
  const [pendingPreset, setPendingPreset] = useState<StrategyPreset | null>(null);
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
  const [toast, setToast] = useState<string | null>(null);
  const writable = user ? canWrite(user) : false;

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
    void (async () => {
      await loadSettings();
    })();
  }, [user, loadSettings]);

  if (loading) {
    return <AuthLoadingShell />;
  }

  if (!user) {
    return null;
  }

  const applyPreset = async (preset: StrategyPreset) => {
    setError(null);
    try {
      const result = controlWriteResultSchema.parse(
        await apiClient.post("/controls/schedule", { windows: preset.windows }),
      );
      if (!result.success) {
        throw new ApiError(result.message, 502);
      }
      setActivePreset(preset);
      setToast(`${preset.label} applied (audit #${result.audit_id})`);
      window.setTimeout(() => setToast(null), 4000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Schedule write failed");
    }
  };

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Automation"
          icon={<GaugeIcon size={22} />}
          title="Time-of-use scheduler"
          description="See your live Sunsynk bands, preview strategies against Agile prices, and apply when writes are enabled."
        />
        {error ? <ErrorBanner message={error} /> : null}
        {toast ? (
          <p className="rounded-xl bg-emerald-500/10 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
            {toast}
          </p>
        ) : null}

        <LiveInverterSettings
          settings={liveSettings}
          loading={settingsLoading}
          error={settingsError}
        />

        {liveSettings && writable && liveSettings.write_allowed ? (
          <>
            <AutoAlignPanel />
            <EditableTouBands
            key={liveSettings.bands.map((b) => `${b.slot}:${b.start}:${b.target_soc_pct}:${b.grid_charge_enabled}:${b.power_w}`).join("|")}
            settings={liveSettings}
            onSubmit={async (bands) => {
              const result = controlWriteResultSchema.parse(
                await apiClient.post("/controls/tou", { bands }),
              );
              if (!result.success) {
                throw new ApiError(result.message, 502);
              }
              setToast(`Schedule written (audit #${result.audit_id})`);
              window.setTimeout(() => setToast(null), 4000);
              await loadSettings();
              return {
                verified: result.verified,
                verification_pending: result.verification_pending,
                verification_message: result.verification_message,
              };
            }}
          />
          </>
        ) : null}

        {liveSettings && !liveSettings.write_allowed ? (
          <InstallerAccessPanel plantName={liveSettings.plant_name || "Greenacre"} />
        ) : null}

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

        {writable ? (
          <section className="solar-card">
            <h3 className="solar-section-title">Strategy modes</h3>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Each preset explains what it does in plain English. Green slots charge, amber
              discharges.
            </p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {STRATEGY_PRESETS.map((preset) => {
                const selected = activePreset.id === preset.id;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => setPendingPreset(preset)}
                    className={`rounded-xl border p-4 text-left transition-all ${
                      selected
                        ? "border-[var(--solar)] bg-amber-500/10 shadow-md"
                        : "border-[var(--border)] bg-[var(--surface)] hover:border-[var(--border-strong)]"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-semibold">{preset.label}</span>
                      <span className="rounded-full border border-[var(--border)] px-2 py-0.5 text-[0.65rem] font-medium uppercase tracking-wide text-[var(--muted)]">
                        {preset.tagline}
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
        ) : (
          <p className="text-sm text-[var(--muted)]">
            Strategy presets require admin access and live writes to be enabled on the backend.
          </p>
        )}

        <ConfirmDialog
          open={pendingPreset != null}
          title={pendingPreset ? `Apply ${pendingPreset.label}?` : "Apply strategy"}
          description={
            pendingPreset
              ? `${pendingPreset.description} This writes TOU slots when live writes are enabled.`
              : "Apply schedule preset."
          }
          confirmLabel="Apply strategy"
          onCancel={() => setPendingPreset(null)}
          onConfirm={() => {
            if (!pendingPreset) return;
            const preset = pendingPreset;
            setPendingPreset(null);
            void applyPreset(preset);
          }}
        />
      </div>
    </AppShell>
  );
}
