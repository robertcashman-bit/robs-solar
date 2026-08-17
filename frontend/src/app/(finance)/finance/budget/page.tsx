"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { BudgetStudio } from "@/components/finance/BudgetStudio";
import { FinanceIntegrityPanel } from "@/components/finance/FinanceIntegrityPanel";
import { HistoryStatsPanel } from "@/components/finance/HistoryStatsPanel";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAuth } from "@/lib/auth-context";
import { canWrite } from "@/lib/permissions";

export default function BudgetPage() {
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
        title="Budget"
        description="Household and business budgets stay separate. Generate from stored history, or choose Stabilise, Balanced, or Debt Attack as an allocation style after essentials."
      />
      <div className="mt-6 space-y-8">
        <FinanceIntegrityPanel canEdit={canWrite(user)} />
        <BudgetStudio user={user} />
        <HistoryStatsPanel />
      </div>
    </AppShell>
  );
}
