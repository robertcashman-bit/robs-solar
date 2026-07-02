"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { FinanceOverviewView } from "@/components/finance/FinanceOverviewView";
import { AppShell } from "@/components/shared/AppShell";
import { AuthLoadingShell } from "@/components/shared/AuthLoadingShell";
import { ErrorBanner } from "@/components/shared/Banners";
import { PageHeader } from "@/components/shared/PageHeader";
import { useAuth } from "@/lib/auth-context";
import { useFinanceOverview } from "@/lib/use-finance-overview";

export default function FinanceOverviewPage() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { overview, loading, error, refresh } = useFinanceOverview(Boolean(user));

  useEffect(() => {
    if (!authLoading && !user) {
      router.replace("/login");
    }
  }, [authLoading, user, router]);

  if (authLoading || !user) {
    return <AuthLoadingShell />;
  }

  return (
    <AppShell>
      <PageHeader
        eyebrow="Finance"
        title="Overview"
        description="Personal and business finances at a glance — balances, debts, cash flow, and alerts."
        actions={
          <button type="button" className="solar-btn-secondary text-sm" onClick={() => void refresh()}>
            Refresh
          </button>
        }
      />
      {error ? <div className="mt-4"><ErrorBanner message={error} /></div> : null}
      {loading && !overview ? (
        <p className="mt-8 text-sm text-[var(--muted)]">Loading finance overview…</p>
      ) : overview ? (
        <div className="mt-6">
          <FinanceOverviewView overview={overview} />
        </div>
      ) : null}
    </AppShell>
  );
}
