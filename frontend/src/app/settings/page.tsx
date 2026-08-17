"use client";

import { useEffect, useState } from "react";

import { BANK_IMPORT_SESSION_KEY } from "@/components/finance/BankImportCard";
import { FinanceSettingsPanel } from "@/components/settings/FinanceSettingsPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner, SuccessBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { ShieldIcon } from "@/components/shared/icons";
import { useRequireAuth } from "@/lib/use-require-auth";
import { canWrite } from "@/lib/permissions";

export default function SettingsPage() {
  const { user, gated, redirecting } = useRequireAuth();
  const [importNotice, setImportNotice] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);


  useEffect(() => {
    const imported = new URLSearchParams(window.location.search).get("imported");
    if (imported !== "1" && imported !== "error") {
      return;
    }
    const timer = window.setTimeout(() => {
      if (imported === "1") {
        window.sessionStorage.setItem(BANK_IMPORT_SESSION_KEY, "1");
        setImportNotice(
          "Bank login complete. Accounts, cards, and Funding Circle payments have been pulled in.",
        );
      } else {
        setImportError(
          "Bank login was saved, but the import did not finish. Use Pull latest from your bank.",
        );
      }
      window.history.replaceState({}, "", "/settings");
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

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
        {importNotice ? <SuccessBanner message={importNotice} /> : null}
        {importError ? <ErrorBanner message={importError} /> : null}
        <FinanceSettingsPanel readOnly={!canWrite(user)} />
      </div>
    </AppShell>
  );
}
