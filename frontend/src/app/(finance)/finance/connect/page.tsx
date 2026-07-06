"use client";

import { Suspense, useEffect } from "react";
import { useRouter } from "next/navigation";

import { BankConnectionsHub } from "@/components/finance/BankConnectionsHub";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAuth } from "@/lib/auth-context";

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
        description="Link Lloyds, MBNA, Virgin Money via Lunch Flow (personal), Capital on Tap (QuickFile), and Funding Circle (manual). Use the menu item Connect banks anytime to return here."
      />
      <div className="mt-6">
        <BankConnectionsHub />
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
