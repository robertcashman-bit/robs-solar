"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { FinanceAssistantPanel } from "@/components/finance/FinanceAssistantPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";

export default function FinanceAssistantPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();

  useEffect(() => {
    if (!authLoading && !user) router.replace("/login");
  }, [authLoading, user, router]);

  if (authLoading || !user) return <AuthLoadingShell />;

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="AI assistant"
        description="Read-only Q&A about your personal and business finances. No changes are made to accounts or settings."
      />
      <div className="mt-6 max-w-3xl">
        <FinanceAssistantPanel canUse={canWrite(user)} />
      </div>
    </AppShell>
  );
}
