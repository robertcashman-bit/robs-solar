"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { AuditTable } from "@/components/audit/AuditTable";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { ShieldIcon } from "@/components/shared/icons";
import { apiClient } from "@/lib/api-client";
import { useAuth } from "@/lib/auth-context";
import { canViewAudit } from "@/lib/permissions";
import { auditListSchema, type AuditEntry } from "@/lib/schemas";

export default function AuditPage() {
  const router = useRouter();
  const { user, loading } = useAuth();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
      return;
    }
    if (!loading && user && !canViewAudit(user)) {
      router.replace("/");
    }
  }, [loading, user, router]);

  useEffect(() => {
    if (!user || !canViewAudit(user)) {
      return;
    }
    void (async () => {
      try {
        const data = auditListSchema.parse(await apiClient.get("/audit"));
        setEntries(data.entries);
      } catch (fetchError) {
        setError(fetchError instanceof Error ? fetchError.message : "Failed to load audit log");
      }
    })();
  }, [user]);

  if (loading) {
    return <AuthLoadingShell />;
  }

  if (!user || !canViewAudit(user)) {
    return null;
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Security"
          icon={<ShieldIcon size={22} />}
          title="Audit log"
          description="Every attempted and successful control action."
        />
        {error ? <ErrorBanner message={error} /> : null}
        <AuditTable entries={entries} />
      </div>
    </AppShell>
  );
}
