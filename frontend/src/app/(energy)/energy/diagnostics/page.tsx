"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { LoadDiagnosticsPanel } from "@/components/diagnostics/LoadDiagnosticsPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { GaugeIcon } from "@/components/shared/icons";
import { useAuth } from "@/lib/auth-context";
import { useLoadDiagnostics } from "@/lib/use-load-diagnostics";

export default function LoadDiagnosticsPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { diagnostics, error, loading, refresh } = useLoadDiagnostics({
    enabled: Boolean(user),
  });

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  if (authLoading) {
    return <AuthLoadingShell />;
  }

  if (!user) {
    return null;
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Troubleshooting"
          icon={<GaugeIcon size={22} />}
          title={<span className="text-gradient-solar">Load diagnostics</span>}
          description="Raw payload, per-field sources, and Measured vs Estimated Load — for when Load looks wrong and you need to see exactly what the inverter/cloud is (and isn't) reporting."
        />
        <LoadDiagnosticsPanel
          diagnostics={diagnostics}
          error={error}
          loading={loading}
          onRefresh={() => void refresh()}
        />
      </div>
    </AppShell>
  );
}
