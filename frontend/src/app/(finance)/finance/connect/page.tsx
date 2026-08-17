"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { BankImportCard } from "@/components/finance/BankImportCard";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { FundingCircleSettingsPanel } from "@/components/settings/FundingCircleSettingsPanel";
import { LunchFlowSettingsPanel } from "@/components/settings/LunchFlowSettingsPanel";
import { OpenBankingSettingsPanel } from "@/components/settings/OpenBankingSettingsPanel";
import { QuickFileSettingsPanel } from "@/components/settings/QuickFileSettingsPanel";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";

export default function ConnectBanksPage() {
  const router = useRouter();
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) return <AuthLoadingShell />;

  const readOnly = !canWrite(user);

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Connect banks"
        description="Link personal banks with TrueLayer or Lunch Flow. QuickFile covers the company. Funding Circle is entered manually."
      />
      <div className="mt-6 space-y-8">
        <section aria-labelledby="open-banking-heading">
          <h2 id="open-banking-heading" className="solar-section-title">
            Open Banking
          </h2>
          <div className="mt-4 space-y-4">
            <BankImportCard readOnly={readOnly} />
            <OpenBankingSettingsPanel readOnly={readOnly} />
          </div>
        </section>
        <section aria-labelledby="lunchflow-heading">
          <h2 id="lunchflow-heading" className="solar-section-title">
            Lunch Flow
          </h2>
          <div className="mt-4">
            <LunchFlowSettingsPanel readOnly={readOnly} />
          </div>
        </section>
        <section aria-labelledby="quickfile-heading">
          <h2 id="quickfile-heading" className="solar-section-title">
            QuickFile
          </h2>
          <div className="mt-4">
            <QuickFileSettingsPanel readOnly={readOnly} />
          </div>
        </section>
        <section aria-labelledby="funding-circle-heading">
          <h2 id="funding-circle-heading" className="solar-section-title">
            Funding Circle
          </h2>
          <div className="mt-4">
            <FundingCircleSettingsPanel readOnly={readOnly} />
          </div>
        </section>
      </div>
    </AppShell>
  );
}
