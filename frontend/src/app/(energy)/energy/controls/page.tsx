"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ExportLimitForm } from "@/components/controls/ExportLimitForm";
import { BatteryControlForm } from "@/components/controls/BatteryControlForm";
import { OperatingModeForm } from "@/components/controls/OperatingModeForm";
import { RulesPanel } from "@/components/controls/RulesPanel";
import { ScheduleForm } from "@/components/controls/ScheduleForm";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { RestoreConfigButton } from "@/components/shared/RestoreConfigButton";
import { GaugeIcon } from "@/components/shared/icons";
import { apiClient, ApiError } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";
import {
  controlWriteResultSchema,
  healthResponseSchema,
  restoreResultSchema,
} from "@/lib/schemas";

export default function ControlsPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [readOnly, setReadOnly] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastAuditId, setLastAuditId] = useState<number | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (!loading && user && !canWrite(user)) {
      router.replace("/");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (!user || !canWrite(user)) {
      return;
    }
    void (async () => {
      try {
        const health = healthResponseSchema.parse(await apiClient.get("/health"));
        setReadOnly(health.read_only);
      } catch (healthError) {
        setError(healthError instanceof Error ? healthError.message : "Failed to load health");
      }
    })();
  }, [user]);

  if (loading) {
    return <AuthLoadingShell />;
  }

  if (!user || !canWrite(user)) {
    return null;
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Operations"
          icon={<GaugeIcon size={22} />}
          title="Controls"
          description="Every write requires confirmation and is audited by the backend."
        />
        {lastAuditId ? (
          <p className="text-sm text-emerald-700 dark:text-emerald-400">
            Last write recorded in{" "}
            <Link href="/settings#audit" className="underline">
              audit log #{lastAuditId}
            </Link>
            .
          </p>
        ) : null}
        {error ? <ErrorBanner message={error} /> : null}
        <ExportLimitForm
          readOnlyMode={readOnly}
          disabled={!canWrite(user)}
          onSubmit={async (limitW) => {
            const result = controlWriteResultSchema.parse(
              await apiClient.post("/controls/export-limit", { limit_w: limitW }),
            );
            if (!result.success) {
              throw new ApiError(result.message, 502);
            }
            setLastAuditId(result.audit_id);
          }}
        />
        <OperatingModeForm
          readOnlyMode={readOnly}
          onSubmit={async (mode) => {
            const result = controlWriteResultSchema.parse(
              await apiClient.post("/controls/operating-mode", { mode }),
            );
            if (!result.success) {
              throw new ApiError(result.message, 502);
            }
            setLastAuditId(result.audit_id);
          }}
        />
        <BatteryControlForm
          readOnlyMode={readOnly}
          disabled={!canWrite(user)}
          onSubmit={async (payload) => {
            const result = controlWriteResultSchema.parse(
              await apiClient.post("/controls/battery", payload),
            );
            if (!result.success) {
              throw new ApiError(result.message, 502);
            }
            setLastAuditId(result.audit_id);
          }}
          onForce={async (action) => {
            const result = controlWriteResultSchema.parse(
              await apiClient.post("/controls/force-battery", { action }),
            );
            if (!result.success) {
              throw new ApiError(result.message, 502);
            }
            setLastAuditId(result.audit_id);
          }}
        />
        <ScheduleForm
          readOnlyMode={readOnly}
          onSubmit={async (windows) => {
            const result = controlWriteResultSchema.parse(
              await apiClient.post("/controls/schedule", { windows }),
            );
            if (!result.success) {
              throw new ApiError(result.message, 502);
            }
            setLastAuditId(result.audit_id);
          }}
        />
        <RulesPanel disabled={readOnly} />
        <RestoreConfigButton
          readOnlyMode={readOnly}
          onRestore={async () => {
            const result = restoreResultSchema.parse(
              await apiClient.post("/config/restore-last-known-good"),
            );
            if (!result.success) {
              throw new ApiError(result.message, 502);
            }
            setLastAuditId(result.audit_id);
          }}
        />
      </div>
    </AppShell>
  );
}
