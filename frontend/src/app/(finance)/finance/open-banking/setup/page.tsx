"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";

import { OpenBankingSetupPage } from "@/components/finance/OpenBankingSetupPage";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";

function OpenBankingSetupContent() {
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
        title="Open Banking Setup"
        description="Plain-English setup for Enable Banking. Save credentials, test the connection, then connect your UK bank accounts."
      />
      <div className="mt-6">
        <OpenBankingSetupPage readOnly={!canWrite(user)} />
      </div>
    </AppShell>
  );
}

export default function OpenBankingSetupRoute() {
  return (
    <Suspense fallback={<AuthLoadingShell />}>
      <OpenBankingSetupContent />
    </Suspense>
  );
}
