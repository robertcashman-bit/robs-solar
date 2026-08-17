"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { AppShortcutPanel } from "@/components/settings/AppShortcutPanel";
import { FinanceSettingsPanel } from "@/components/settings/FinanceSettingsPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { ShieldIcon } from "@/components/shared/icons";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";

export default function SettingsPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [loading, user, router]);

  if (loading) {
    return <AuthLoadingShell />;
  }

  if (!user) {
    return null;
  }

  return (
    <AppShell>
      <div className="space-y-6">
        <PageHeader
          eyebrow="Configuration"
          icon={<ShieldIcon size={22} />}
          title="Settings"
          description="Finance integrations, banking connections, and account preferences."
        />
        <FinanceSettingsPanel readOnly={!canWrite(user)} />
        <AppShortcutPanel />
      </div>
    </AppShell>
  );
}
