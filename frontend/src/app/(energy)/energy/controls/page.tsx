"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { LiveInverterSettings } from "@/components/scheduler/LiveInverterSettings";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { InfoBanner } from "@/components/shared/InfoBanner";
import { PageHeader } from "@/components/shared/PageHeader";
import { GaugeIcon } from "@/components/shared/icons";
import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { inverterSettingsSchema, type InverterSettings } from "@/lib/schemas";

export default function ControlsPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [settings, setSettings] = useState<InverterSettings | null>(null);
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsError, setSettingsError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  const loadSettings = useCallback(async () => {
    setSettingsLoading(true);
    setSettingsError(null);
    try {
      const data = await apiClient.get("/controls/settings");
      setSettings(inverterSettingsSchema.parse(data));
    } catch (e) {
      setSettings(null);
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

  if (loading || !user) {
    return <AuthLoadingShell />;
  }

  return (
    <AppShell>
      <div className="solar-page">
        <PageHeader
          eyebrow="Energy"
          icon={<GaugeIcon size={22} />}
          title="Inverter settings"
          description="Live read-only view of your Sunsynk schedule and operating mode. This app does not change inverter settings."
          actions={
            <button type="button" className="solar-btn-secondary text-sm" onClick={() => void loadSettings()}>
              Refresh
            </button>
          }
        />
        <InfoBanner>
          Display only — use Simple Solar or Sunsynk Connect if you need to change charge/discharge
          limits, TOU bands, or operating mode.
        </InfoBanner>
        <LiveInverterSettings
          settings={settings}
          loading={settingsLoading}
          error={settingsError}
        />
      </div>
    </AppShell>
  );
}
