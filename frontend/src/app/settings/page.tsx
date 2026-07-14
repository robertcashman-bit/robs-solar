"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { InfoBanner } from "@/components/shared/InfoBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { PageLoading } from "@/components/shared/PageLoading";
import { StatusBadge } from "@/components/shared/StatusBadge";
import { SettingsIcon, ShieldIcon } from "@/components/shared/icons";
import { FinanceSettingsPanel } from "@/components/settings/FinanceSettingsPanel";
import { OctopusSettingsForm } from "@/components/settings/OctopusSettingsForm";
import { InstallerAccessPanel } from "@/components/settings/InstallerAccessPanel";
import { TariffSettingsForm } from "@/components/settings/TariffSettingsForm";
import { NotificationSettingsForm } from "@/components/settings/NotificationSettingsForm";
import { OptimisationModePanel } from "@/components/settings/OptimisationModePanel";
import { RemoteAccessPanel } from "@/components/settings/RemoteAccessPanel";
import { SafetySettingsPanel } from "@/components/settings/SafetySettingsPanel";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";
import {
  auditListSchema,
  capabilitiesResponseSchema,
  octopusConfigStatusSchema,
  tariffSettingsSchema,
  inverterSettingsSchema,
  type OctopusConfigStatus,
  notificationSettingsStatusSchema,
  safetySettingsSchema,
  type NotificationSettingsStatus,
  type SafetySettings,
  optimisationModeSchema,
  type OptimisationModeSettings,
  type TariffSettings,
} from "@/lib/schemas";

const ENERGY_SECTIONS = [
  { id: "energy-status", label: "System status" },
  { id: "energy-hardware", label: "Hardware" },
  { id: "energy-tariff", label: "Tariff" },
  { id: "energy-integrations", label: "Integrations" },
  { id: "energy-safety", label: "Safety" },
  { id: "energy-backup", label: "Backup" },
] as const;

export default function SettingsPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [settingsTab, setSettingsTab] = useState<"finance" | "energy">("finance");
  const [error, setError] = useState<string | null>(null);
  const [capabilities, setCapabilities] = useState<ReturnType<
    typeof capabilitiesResponseSchema.parse
  > | null>(null);
  const [tariff, setTariff] = useState<TariffSettings | null>(null);
  const [octopus, setOctopus] = useState<OctopusConfigStatus | null>(null);
  const [inverterAccess, setInverterAccess] = useState(
    null as ReturnType<typeof inverterSettingsSchema.parse> | null,
  );
  const [safety, setSafety] = useState<SafetySettings | null>(null);
  const [notifications, setNotifications] = useState<NotificationSettingsStatus | null>(null);
  const [optimisationMode, setOptimisationMode] = useState<OptimisationModeSettings | null>(null);
  const [auditPreview, setAuditPreview] = useState<string[]>([]);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (!user) {
      return;
    }
    void (async () => {
      try {
        const [capsData, tariffData, inverterData] = await Promise.all([
          apiClient.get("/capabilities"),
          apiClient.get("/tariff"),
          apiClient.get("/controls/settings").catch(() => null),
        ]);
        setCapabilities(capabilitiesResponseSchema.parse(capsData));
        setTariff(tariffSettingsSchema.parse(tariffData));
        if (inverterData) {
          setInverterAccess(inverterSettingsSchema.parse(inverterData));
        }
        if (canWrite(user)) {
          const [auditData, octopusData, safetyData, notifyData, optModeData] = await Promise.all([
            apiClient.get("/audit?limit=20"),
            apiClient.get("/octopus/settings").catch(() => null),
            apiClient.get("/config/safety").catch(() => null),
            apiClient.get("/settings/notifications").catch(() => null),
            apiClient.get("/optimisation/mode").catch(() => null),
          ]);
          setAuditPreview(
            auditListSchema.parse(auditData).entries.map(
              (e) => `${e.timestamp} · ${e.action} · ${e.outcome}`,
            ),
          );
          if (octopusData) {
            setOctopus(octopusConfigStatusSchema.parse(octopusData));
          }
          if (safetyData) {
            setSafety(safetySettingsSchema.parse(safetyData));
          }
          if (notifyData) {
            setNotifications(notificationSettingsStatusSchema.parse(notifyData));
          }
          if (optModeData) {
            setOptimisationMode(optimisationModeSchema.parse(optModeData));
          }
        }
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load settings");
      }
    })();
  }, [user]);

  if (loading) {
    return <AuthLoadingShell />;
  }

  if (!user) {
    return null;
  }

  const liveWritesEnabled = capabilities?.enable_live_writes ?? false;
  const isSimulated = capabilities?.data_source === "simulated";

  return (
    <AppShell>
      <div className="solar-page">
        <PageHeader
          eyebrow="Configuration"
          icon={<ShieldIcon size={22} />}
          title="Safety & configuration"
          description="Manage finance integrations and energy system settings. Live writes remain opt-in via environment variables."
        />

        {error ? <ErrorBanner message={error} /> : null}

        <div
          role="tablist"
          aria-label="Settings sections"
          className="flex gap-2 rounded-xl border border-[var(--border)] bg-[var(--surface)] p-1"
        >
          <button
            type="button"
            role="tab"
            aria-selected={settingsTab === "finance"}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              settingsTab === "finance" ? "bg-emerald-500 text-white" : "text-[var(--muted)]"
            }`}
            onClick={() => setSettingsTab("finance")}
          >
            Finance
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={settingsTab === "energy"}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              settingsTab === "energy" ? "bg-amber-500 text-white" : "text-[var(--muted)]"
            }`}
            onClick={() => setSettingsTab("energy")}
          >
            Energy / Solar
          </button>
        </div>

        {settingsTab === "finance" ? <FinanceSettingsPanel readOnly={!canWrite(user)} /> : null}

        {settingsTab === "energy" ? (
          <>
            <nav aria-label="Energy settings sections" className="flex flex-wrap gap-2">
              {ENERGY_SECTIONS.map((section) => (
                <a
                  key={section.id}
                  href={`#${section.id}`}
                  className="rounded-full border border-[var(--border)] bg-[var(--surface)] px-3 py-1 text-xs font-medium text-[var(--muted)] transition-colors hover:text-[var(--foreground)]"
                >
                  {section.label}
                </a>
              ))}
            </nav>

        {inverterAccess && !inverterAccess.write_allowed ? (
          <InstallerAccessPanel plantName={inverterAccess.plant_name || "Greenacre"} />
        ) : null}

        {!liveWritesEnabled ? (
          <InfoBanner variant="warning">
            Live writes disabled — set ENABLE_LIVE_WRITES=true (and Sunsynk unverified flag if using
            Sunsynk) in backend/.env to allow non-simulator live writes.
          </InfoBanner>
        ) : null}

        {capabilities?.read_only ? (
          <InfoBanner variant="info">
            Read-only mode is enabled — all control writes are blocked at the API layer.
          </InfoBanner>
        ) : null}

        {capabilities ? (
          <RemoteAccessPanel
            readOnly={capabilities.read_only}
            liveWritesEnabled={capabilities.enable_live_writes}
            adapterMode={capabilities.adapter.mode}
          />
        ) : null}

        {capabilities ? (
          <section id="energy-status" className="solar-card scroll-mt-24">
            <h3 className="solar-section-title">System status</h3>
            <div className="mt-4 flex flex-wrap gap-2">
              <StatusBadge
                label={capabilities.read_only ? "Read-only" : "Writes allowed"}
                tone={capabilities.read_only ? "warning" : "positive"}
              />
              <StatusBadge
                label={capabilities.enable_live_writes ? "Live writes on" : "Live writes off"}
                tone={capabilities.enable_live_writes ? "positive" : "warning"}
              />
              <StatusBadge
                label={
                  capabilities.sunsynk_enable_unverified_writes
                    ? "Sunsynk writes on"
                    : "Sunsynk writes off"
                }
                tone={capabilities.sunsynk_enable_unverified_writes ? "positive" : "warning"}
              />
            </div>
            <dl className="grid gap-5 sm:grid-cols-2">
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                <dt className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
                  <SettingsIcon size={14} />
                  Adapter mode
                </dt>
                <dd className="mt-1 text-lg font-semibold">{capabilities.adapter.mode}</dd>
              </div>
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                <dt className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
                  Data source
                </dt>
                <dd className="mt-1 text-lg font-semibold">
                  {isSimulated ? "Simulated data" : "Live data"}
                </dd>
              </div>
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                <dt className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
                  Supported writes
                </dt>
                <dd className="mt-1 font-medium">
                  {capabilities.adapter.supported_writes.length > 0
                    ? capabilities.adapter.supported_writes.join(", ")
                    : "None"}
                </dd>
              </div>
              {capabilities.plant_id ? (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                  <dt className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
                    Plant ID
                  </dt>
                  <dd className="mt-1 font-mono font-medium">{capabilities.plant_id}</dd>
                </div>
              ) : null}
              {capabilities.modbus_host ? (
                <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                  <dt className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
                    Modbus TCP
                  </dt>
                  <dd className="mt-1 font-mono text-sm">
                    {capabilities.modbus_host}:{capabilities.modbus_port} (slave{" "}
                    {capabilities.modbus_slave_id})
                  </dd>
                  <dd className="text-xs text-[var(--muted)]">
                    Live poll {capabilities.poll_interval_live_seconds}s · energy{" "}
                    {capabilities.poll_interval_energy_seconds}s
                  </dd>
                </div>
              ) : null}
              <div className="rounded-xl border border-[var(--border)] bg-[var(--surface)] p-4">
                <dt className="text-xs font-medium uppercase tracking-wider text-[var(--muted)]">
                  Octopus API
                </dt>
                <dd className="mt-1 font-medium">
                  {capabilities.octopus_configured ? "Connected" : "Not configured"}
                </dd>
              </div>
            </dl>
          </section>
        ) : (
          <PageLoading label="Loading configuration" rows={1} />
        )}

        <section id="energy-hardware" className="solar-card scroll-mt-24">
          <h3 className="solar-section-title">System hardware</h3>
          <dl className="mt-3 grid gap-2 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-[var(--muted)]">Inverter</dt>
              <dd className="font-medium">Sunsynk SunC2-8.0LV01W (E4AM25800311)</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Battery</dt>
              <dd className="font-medium">Fogstar Drift 16.1 kWh (A2613000ED)</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Wi-Fi dongle</dt>
              <dd className="font-medium">2601315599</dd>
            </div>
            <div>
              <dt className="text-[var(--muted)]">Panels</dt>
              <dd className="font-medium">22 × Aiko 480 W (~10.56 kWp)</dd>
            </div>
          </dl>
          <p className="mt-3 text-xs text-[var(--muted)]">
            Modbus: set MODBUS_HOST in backend/.env and ADAPTER_MODE=modbus_tcp. Run{" "}
            <code className="rounded bg-[var(--surface-sunken)] px-1">python scripts/discover_modbus.py</code>{" "}
            to scan your LAN.
          </p>
        </section>

        {tariff ? (
          <div id="energy-tariff" className="scroll-mt-24">
            <TariffSettingsForm
            initial={tariff}
            readOnly={!canWrite(user)}
            onSubmit={async (updated) => {
              const result = tariffSettingsSchema.parse(
                await apiClient.put("/tariff", updated),
              );
              setTariff(result);
            }}
          />
          </div>
        ) : null}

        {canWrite(user) && octopus ? (
          <div id="energy-integrations" className="scroll-mt-24">
            <OctopusSettingsForm initial={octopus} onSaved={(status) => setOctopus(status)} />
          </div>
        ) : null}

        {canWrite(user) && notifications ? (
          <NotificationSettingsForm
            initial={notifications}
            onSubmit={async (payload) => {
              const result = notificationSettingsStatusSchema.parse(
                await apiClient.put("/settings/notifications", payload),
              );
              setNotifications(result);
            }}
          />
        ) : null}

        {canWrite(user) && safety ? (
          <div id="energy-safety" className="scroll-mt-24">
            <SafetySettingsPanel
            initial={safety}
            onSubmit={async (update) => {
              const result = safetySettingsSchema.parse(
                await apiClient.put("/config/safety", update),
              );
              setSafety(result);
              const capsData = await apiClient.get("/capabilities");
              setCapabilities(capabilitiesResponseSchema.parse(capsData));
            }}
          />
          </div>
        ) : null}

        {canWrite(user) && optimisationMode ? (
          <OptimisationModePanel initial={optimisationMode} readOnly={!canWrite(user)} />
        ) : null}

        {canWrite(user) ? (
          <section id="energy-backup" className="solar-card scroll-mt-24 space-y-3">
            <h3 className="solar-section-title">Configuration backup</h3>
            <p className="text-sm text-[var(--muted)]">
              Export tariff and recent snapshots as JSON. Restore applies tariff only (adapter mode
              remains env-controlled).
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="solar-btn-ghost"
                onClick={() =>
                  void apiClient.get<unknown>("/config/backup").then((data) => {
                    const blob = new Blob([JSON.stringify(data, null, 2)], {
                      type: "application/json",
                    });
                    const url = URL.createObjectURL(blob);
                    const link = document.createElement("a");
                    link.href = url;
                    link.download = `robs-solar-backup-${Date.now()}.json`;
                    link.click();
                    URL.revokeObjectURL(url);
                  })
                }
              >
                Download backup
              </button>
              <label className="solar-btn-ghost cursor-pointer">
                Restore from file
                <input
                  type="file"
                  accept="application/json"
                  className="hidden"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (!file) return;
                    void file.text().then((text) => {
                      const payload = JSON.parse(text) as {
                        tariff: TariffSettings;
                        adapter_mode: string;
                        snapshots?: unknown[];
                      };
                      return apiClient.post("/config/backup/restore", payload);
                    });
                  }}
                />
              </label>
            </div>
          </section>
        ) : null}

        {auditPreview.length ? (
          <section id="audit" className="solar-card">
            <h3 className="solar-section-title">Recent Modbus / control log</h3>
            <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto font-mono text-xs text-[var(--muted)]">
              {auditPreview.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        ) : null}
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
