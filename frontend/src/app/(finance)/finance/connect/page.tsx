"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";

import { BankConnectionsHub } from "@/components/finance/BankConnectionsHub";
import { OpenBankingSetupPage } from "@/components/finance/OpenBankingSetupPage";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";

function ConnectBanksContent() {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) return <AuthLoadingShell />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Connect banks"
        description="Set up Open Banking credentials, then link Lloyds, MBNA, Virgin Money, Capital on Tap, and Funding Circle. Lunch Flow is used for personal banks when configured."
      />
      <div className="mt-6 space-y-10">
        <section id="open-banking-setup" aria-labelledby="open-banking-setup-heading">
          <h2 id="open-banking-setup-heading" className="sr-only">
            Open Banking setup
          </h2>
          <OpenBankingSetupPage readOnly={!canWrite(user)} handleOAuthCallback={false} />
        </section>
        <section aria-labelledby="bank-connections-heading">
          <h2 id="bank-connections-heading" className="sr-only">
            Linked bank accounts
          </h2>
          <BankConnectionsHub readOnly={!canWrite(user)} />
        </section>
      </div>
    </AppShell>
  );
}

export default function ConnectBanksPage() {
  return (
    <Suspense fallback={<AuthLoadingShell />}>
      <ConnectBanksContent />
    </Suspense>
  );
}
