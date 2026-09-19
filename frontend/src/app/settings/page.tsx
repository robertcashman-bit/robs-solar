"use client";

import { FinanceSettingsPanel } from "@/components/settings/FinanceSettingsPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { ShieldIcon } from "@/components/shared/icons";
import { useRequireAuth } from "@/lib/use-require-auth";
import { canWrite } from "@/lib/permissions";

export default function SettingsPage() {
  const { user, gated, redirecting } = useRequireAuth();

  if (gated) {
    return <AuthLoadingShell redirecting={redirecting} />;
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
      </div>
    </AppShell>
  );
}
