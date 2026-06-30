"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AppShell } from "@/components/shared/AppShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { SettingsIcon, ShieldIcon } from "@/components/shared/icons";
import { OctopusSettingsForm } from "@/components/settings/OctopusSettingsForm";
import { InstallerAccessPanel } from "@/components/settings/InstallerAccessPanel";
import { TariffSettingsForm } from "@/components/settings/TariffSettingsForm";
import { NotificationSettingsForm } from "@/components/settings/NotificationSettingsForm";
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
  type TariffSettings,
} from "@/lib/schemas";

function StatusBadge({ enabled, label }: { enabled: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
        enabled
          ? "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-300"
          : "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-300"
      }`}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${enabled ? "bg-emerald-500" : "bg-amber-500"}`} />
      {label}
    </span>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
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
          const [auditData, octopusData, safetyData, notifyData] = await Promise.all([
            apiClient.get("/audit?limit=20"),
            apiClient.get("/octopus/settings").catch(() => null),
            apiClient.get("/config/safety").catch(() => null),
            apiClient.get("/settings/notifications").catch(() => null),
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
        }
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load settings");
      }
    })();
  }, [user]);

  if (loading || !user) {
    return null;
  }

  const liveWritesEnabled = capabilities?.enable_live_writes ?? false;
  const isSimulated = capabilities?.data_source === "simulated";

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Configuration"
          icon={<ShieldIcon size={22} />}
          title="Safety & configuration"
          description="Backend adapter mode and safety flags. Live writes remain opt-in via environment variables."
        />

        {error ? <ErrorBanner message={error} /> : null}

        {inverterAccess && !inverterAccess.write_allowed ? (
          <InstallerAccessPanel plantName={inverterAccess.plant_name || "Greenacre"} />
        ) : null}

        {!liveWritesEnabled ? (
          <p className="rounded-xl border border-amber-300/40 bg-amber-50/80 px-4 py-3 text-sm text-amber-900 dark:bg-amber-950/30 dark:text-amber-200">
            Live writes disabled — set ENABLE_LIVE_WRITES=true (and Sunsynk unverified flag if using
            Sunsynk) in backend/.env to allow non-simulator live writes.
          </p>
        ) : null}

        {capabilities?.read_only ? (
          <p className="rounded-xl border border-sky-300/40 bg-sky-50/80 px-4 py-3 text-sm text-sky-900 dark:bg-sky-950/30 dark:text-sky-200">
            Read-only mode is enabled — all control writes are blocked at the API layer.
          </p>
        ) : null}

        {capabilities ? (
          <section className="solar-card">
            <div className="mb-4 flex flex-wrap gap-2">
              <StatusBadge enabled={!capabilities.read_only} label={capabilities.read_only ? "Read-only" : "Writes allowed"} />
              <StatusBadge enabled={capabilities.enable_live_writes} label={capabilities.enable_live_writes ? "Live writes on" : "Live writes off"} />
              <StatusBadge enabled={capabilities.sunsynk_enable_unverified_writes} label={capabilities.sunsynk_enable_unverified_writes ? "Sunsynk writes on" : "Sunsynk writes off"} />
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
          <p className="text-sm text-[var(--muted)]">Loading configuration...</p>
        )}

        <section className="solar-card">
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
        ) : null}

        {canWrite(user) && octopus ? (
          <OctopusSettingsForm initial={octopus} onSaved={(status) => setOctopus(status)} />
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
        ) : null}

        {canWrite(user) ? (
          <section className="solar-card space-y-3">
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
          <section className="solar-card">
            <h3 className="solar-section-title">Recent Modbus / control log</h3>
            <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto font-mono text-xs text-[var(--muted)]">
              {auditPreview.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </AppShell>
  );
}
